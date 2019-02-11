"""
Copyright 2018 Grid Singularity
This file is part of D3A.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
import random
from pendulum import duration
from typing import Union
from collections import namedtuple

from d3a.d3a_core.util import generate_market_slot_list
from d3a.d3a_core.exceptions import MarketException
from d3a.models.state import LoadState
from d3a.models.strategy import BaseStrategy
from d3a.models.const import ConstSettings
from d3a.models.strategy.update_frequency import BidUpdateFrequencyMixin
from d3a.d3a_core.device_registry import DeviceRegistry
from d3a.models.read_user_profile import read_arbitrary_profile
from d3a.models.read_user_profile import InputProfileTypes

BalancingRatio = namedtuple('BalancingRatio', ('demand', 'supply'))


class LoadHoursStrategy(BaseStrategy, BidUpdateFrequencyMixin):
    parameters = ('avg_power_W', 'hrs_per_day', 'hrs_of_day', 'final_buying_rate')

    def __init__(self, avg_power_W, hrs_per_day=None, hrs_of_day=None, daily_budget=None,
                 initial_buying_rate: Union[float, dict, str] =
                 ConstSettings.LoadSettings.INITIAL_BUYING_RATE,
                 final_buying_rate: Union[float, dict, str] =
                 ConstSettings.LoadSettings.FINAL_BUYING_RATE,
                 balancing_energy_ratio: tuple =
                 (ConstSettings.BalancingSettings.OFFER_DEMAND_RATIO,
                  ConstSettings.BalancingSettings.OFFER_SUPPLY_RATIO)):

        BaseStrategy.__init__(self)
        self.initial_buying_rate = read_arbitrary_profile(InputProfileTypes.IDENTITY,
                                                          initial_buying_rate)
        self.final_buying_rate = read_arbitrary_profile(InputProfileTypes.IDENTITY,
                                                        final_buying_rate)
        BidUpdateFrequencyMixin.__init__(self,
                                         initial_rate_profile=self.initial_buying_rate,
                                         final_rate_profile=self.final_buying_rate)
        self.state = LoadState()
        self.avg_power_W = avg_power_W

        # consolidated_cycle is KWh energy consumed for the entire year
        self.daily_energy_required = None
        # Budget for a single day in eur
        self.daily_budget = daily_budget * 100 if daily_budget is not None else None
        # Energy consumed during the day ideally should not exceed daily_energy_required
        self.energy_per_slot_Wh = None
        self.energy_requirement_Wh = {}  # type: Dict[Time, float]
        self.hrs_per_day = {}  # type: Dict[int, int]

        self.assign_hours_of_per_day(hrs_of_day, hrs_per_day)
        self.balancing_energy_ratio = BalancingRatio(*balancing_energy_ratio)

    @property
    def active_markets(self):
        markets = []
        for market in self.area.all_markets:
            if self._allowed_operating_hours(market.time_slot):
                markets.append(market)
        return markets

    def assign_hours_of_per_day(self, hrs_of_day, hrs_per_day):
        if hrs_of_day is None:
            hrs_of_day = list(range(24))

        # be a parameter on the constructor or if we want to deal in percentages
        if hrs_per_day is None:
            hrs_per_day = len(hrs_of_day)
        if hrs_of_day is None:
            hrs_of_day = list(range(24))
        self.hrs_of_day = hrs_of_day
        self._initial_hrs_per_day = hrs_per_day

        if not all([0 <= h <= 23 for h in hrs_of_day]):
            raise ValueError("Hrs_of_day list should contain integers between 0 and 23.")

        if len(hrs_of_day) < hrs_per_day:
            raise ValueError("Length of list 'hrs_of_day' must be greater equal 'hrs_per_day'")

    def assign_energy_requirement(self, avg_power_W):
        self.energy_per_slot_Wh = (avg_power_W /
                                   (duration(hours=1) / self.area.config.slot_length))
        for slot_time in generate_market_slot_list(self.area):
            if self._allowed_operating_hours(slot_time) and slot_time >= self.area.now:
                self.energy_requirement_Wh[slot_time] = self.energy_per_slot_Wh
                self.state.desired_energy_Wh[slot_time] = self.energy_per_slot_Wh

    def event_activate(self):
        if ConstSettings.IAASettings.AlternativePricing.PRICING_SCHEME != 0:
            self.initial_buying_rate = read_arbitrary_profile(InputProfileTypes.IDENTITY, 0)
            self.final_buying_rate = read_arbitrary_profile(
                InputProfileTypes.IDENTITY, self.area.config.market_maker_rate)

        self.hrs_per_day = {day: self._initial_hrs_per_day
                            for day in range(self.area.config.sim_duration.days + 1)}
        self._simulation_start_timestamp = self.area.now
        self.assign_energy_requirement(self.avg_power_W)

    def area_reconfigure_event(self, avg_power_W=None, hrs_per_day=None,
                               hrs_of_day=None, final_buying_rate=None):
        if hrs_per_day is not None or hrs_of_day is not None:
            self.assign_hours_of_per_day(hrs_of_day, hrs_per_day)
            self.hrs_per_day = {day: self._initial_hrs_per_day
                                for day in range(self.area.config.sim_duration.days + 1)}

        if avg_power_W is not None:
            self.avg_power_W = avg_power_W
            self.assign_energy_requirement(avg_power_W)

        if final_buying_rate is not None:
            self.final_buying_rate = read_arbitrary_profile(InputProfileTypes.IDENTITY,
                                                            final_buying_rate)
            self._final_rate_profile = self.final_buying_rate

    def _find_acceptable_offer(self, market):
        offers = market.most_affordable_offers
        return random.choice(offers)

    def _one_sided_market_event_tick(self, market):
        try:
            if len(market.sorted_offers) < 1:
                return
            acceptable_offer = self._find_acceptable_offer(market)

            if acceptable_offer and \
                    self.initial_buying_rate[market.time_slot] <= \
                    round(acceptable_offer.price / acceptable_offer.energy, 8) <= \
                    self.final_buying_rate[market.time_slot]:
                max_energy = self.energy_requirement_Wh[market.time_slot] / 1000.0
                current_day = self._get_day_of_timestamp(market.time_slot)
                if acceptable_offer.energy > max_energy:
                    self.accept_offer(market, acceptable_offer, energy=max_energy)
                    self.energy_requirement_Wh[market.time_slot] = 0
                    self.hrs_per_day[current_day] -= self._operating_hours(max_energy)
                else:
                    self.accept_offer(market, acceptable_offer)
                    self.energy_requirement_Wh[market.time_slot] -= \
                        acceptable_offer.energy * 1000.0
                    self.hrs_per_day[current_day] -= self._operating_hours(acceptable_offer.energy)

        except MarketException:
            self.log.exception("An Error occurred while buying an offer")

    def _get_day_of_timestamp(self, time_slot):
        return (time_slot - self._simulation_start_timestamp).days

    def _double_sided_market_event_tick(self, market):
        if self.are_bids_posted(market):
            self.update_posted_bids_over_ticks(market)

    def event_tick(self, *, area):
        for market in self.active_markets:
            if self.energy_requirement_Wh[market.time_slot] <= 0:
                continue
            if market.time_slot not in self.energy_requirement_Wh:
                continue

            if ConstSettings.IAASettings.MARKET_TYPE == 1:
                self._one_sided_market_event_tick(market)
            elif ConstSettings.IAASettings.MARKET_TYPE == 2 or \
                    ConstSettings.IAASettings.MARKET_TYPE == 3:
                self._double_sided_market_event_tick(market)

    def _allowed_operating_hours(self, time):
        return time.hour in self.hrs_of_day

    def _operating_hours(self, energy):
        return (((energy * 1000) / self.energy_per_slot_Wh)
                * (self.area.config.slot_length / duration(hours=1)))

    def event_market_cycle(self):
        for market in self.active_markets:
            current_day = self._get_day_of_timestamp(market.time_slot)
            if self.hrs_per_day[current_day] <= 0:
                self.energy_requirement_Wh[market.time_slot] = 0.0
                self.state.desired_energy_Wh[market.time_slot] = 0.0

            if ConstSettings.IAASettings.MARKET_TYPE == 2 or \
                    ConstSettings.IAASettings.MARKET_TYPE == 3:
                if self.energy_requirement_Wh[market.time_slot] > 0:
                    if self.is_eligible_for_balancing_market:
                        bid_energy = \
                            self.energy_requirement_Wh[market.time_slot] - \
                            self.balancing_energy_ratio.demand * \
                            self.state.desired_energy_Wh[market.time_slot]
                    else:
                        bid_energy = self.energy_requirement_Wh[market.time_slot]
                    if not self.are_bids_posted(market):
                        self.post_first_bid(market, bid_energy)
        self.update_market_cycle_bids()

    def event_balancing_market_cycle(self):
        for market in self.active_markets:
            self._demand_balancing_offer(market)

    def event_bid_deleted(self, *, market_id, bid):
        market = self.area.get_future_market_from_id(market_id)
        assert market is not None

        if bid.buyer != self.owner.name:
            return
        self.remove_bid_from_pending(bid.id, market)

    def event_bid_traded(self, *, market_id, bid_trade):
        market = self.area.get_future_market_from_id(market_id)
        assert market is not None

        if bid_trade.buyer != self.owner.name:
            return

        buffered_bid = next(filter(
            lambda b: b.id == bid_trade.offer.id,
            self.get_posted_bids(market)
        ))

        if bid_trade.offer.buyer == buffered_bid.buyer:
            self.energy_requirement_Wh[market.time_slot] -= bid_trade.offer.energy * 1000.0
            self.hrs_per_day[self._get_day_of_timestamp(market.time_slot)] -= \
                self._operating_hours(bid_trade.offer.energy)
            if not bid_trade.residual or self.energy_requirement_Wh[market.time_slot] < 0.00001:
                self.remove_bid_from_pending(bid_trade.offer.id, market)
            assert self.energy_requirement_Wh[market.time_slot] >= -0.00001

        super().event_bid_traded(market_id=market_id, bid_trade=bid_trade)

    def event_trade(self, *, market_id, trade):
        market = self.area.get_future_market_from_id(market_id)
        assert market is not None

        if ConstSettings.BalancingSettings.FLEXIBLE_LOADS_SUPPORT:
            # Load can only put supply_balancing_offers only when there is a trade in spot_market
            self._supply_balancing_offer(market, trade)
        super().event_trade(market_id=market_id, trade=trade)

    # committing to increase its consumption when required
    def _demand_balancing_offer(self, market):
        if not self.is_eligible_for_balancing_market:
            return

        ramp_up_energy = \
            self.balancing_energy_ratio.demand * \
            self.state.desired_energy_Wh[market.time_slot]
        self.energy_requirement_Wh[market.time_slot] -= ramp_up_energy
        ramp_up_price = DeviceRegistry.REGISTRY[self.owner.name][0] * ramp_up_energy
        if ramp_up_energy != 0 and ramp_up_price != 0:
            self.area.get_balancing_market(market.time_slot). \
                balancing_offer(ramp_up_price,
                                -ramp_up_energy,
                                self.owner.name)

    # committing to reduce its consumption when required
    def _supply_balancing_offer(self, market, trade):
        if not self.is_eligible_for_balancing_market:
            return
        if trade.buyer != self.owner.name:
            return
        ramp_down_energy = self.balancing_energy_ratio.supply * trade.offer.energy
        ramp_down_price = DeviceRegistry.REGISTRY[self.owner.name][1] * ramp_down_energy
        self.area.get_balancing_market(market.time_slot).balancing_offer(ramp_down_price,
                                                                         ramp_down_energy,
                                                                         self.owner.name)


class CellTowerLoadHoursStrategy(LoadHoursStrategy):
    pass
