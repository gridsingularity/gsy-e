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
from numpy import random
from pendulum import duration, DateTime  # NOQA
from typing import Union, Dict  # NOQA
from collections import namedtuple
from d3a.d3a_core.util import generate_market_slot_list
from d3a.d3a_core.exceptions import MarketException
from d3a.models.state import LoadState
from d3a.models.strategy import BidEnabledStrategy
from d3a_interface.constants_limits import ConstSettings
from d3a_interface.device_validator import validate_load_device_price, validate_load_device_energy
from d3a.models.strategy.update_frequency import UpdateFrequencyMixin
from d3a.d3a_core.device_registry import DeviceRegistry
from d3a.models.read_user_profile import read_arbitrary_profile
from d3a.models.read_user_profile import InputProfileTypes
from d3a.constants import FLOATING_POINT_TOLERANCE
from d3a_interface.constants_limits import GlobalConfig
from d3a_interface.utils import key_in_dict_and_not_none

BalancingRatio = namedtuple('BalancingRatio', ('demand', 'supply'))


class LoadHoursStrategy(BidEnabledStrategy):
    parameters = ('avg_power_W', 'hrs_per_day', 'hrs_of_day', 'fit_to_limit',
                  'energy_rate_increase_per_update', 'update_interval', 'initial_buying_rate',
                  'final_buying_rate', 'balancing_energy_ratio', 'use_market_maker_rate')

    def __init__(self, avg_power_W, hrs_per_day=None, hrs_of_day=None,
                 fit_to_limit=True, energy_rate_increase_per_update=None,
                 update_interval=None,
                 initial_buying_rate: Union[float, dict, str] =
                 ConstSettings.LoadSettings.BUYING_RATE_RANGE.initial,
                 final_buying_rate: Union[float, dict, str] =
                 ConstSettings.LoadSettings.BUYING_RATE_RANGE.final,
                 balancing_energy_ratio: tuple =
                 (ConstSettings.BalancingSettings.OFFER_DEMAND_RATIO,
                  ConstSettings.BalancingSettings.OFFER_SUPPLY_RATIO),
                 use_market_maker_rate: bool = False):
        """
        Constructor of LoadHoursStrategy
        :param avg_power_W: Power rating of load device
        :param hrs_per_day: Daily energy usage
        :param hrs_of_day: hours of day energy is needed
        :param fit_to_limit: if set to True, it will make a linear curve
        following following initial_buying_rate & final_buying_rate
        :param energy_rate_increase_per_update: Slope of Load bids change per update
        :param update_interval: Interval after which Load will update its offer
        :param initial_buying_rate: Starting point of load's preferred buying rate
        :param final_buying_rate: Ending point of load's preferred buying rate
        :param use_market_maker_rate: If set to True, Load would track its final buying rate
        as per utility's trading rate
        """

        validate_load_device_energy(avg_power_W=avg_power_W, hrs_per_day=hrs_per_day,
                                    hrs_of_day=hrs_of_day)
        self.state = LoadState()
        self.avg_power_W = avg_power_W

        # consolidated_cycle is KWh energy consumed for the entire year
        self.daily_energy_required = None
        # Energy consumed during the day ideally should not exceed daily_energy_required
        self.energy_per_slot_Wh = None
        self.energy_requirement_Wh = {}  # type: Dict[DateTime, float]
        self.hrs_per_day = {}  # type: Dict[int, int]

        self.assign_hours_of_per_day(hrs_of_day, hrs_per_day)
        self.balancing_energy_ratio = BalancingRatio(*balancing_energy_ratio)

        self._init_price_update(fit_to_limit, energy_rate_increase_per_update, update_interval,
                                use_market_maker_rate, initial_buying_rate, final_buying_rate)
        self._calculate_active_markets()

    def _init_price_update(self, fit_to_limit, energy_rate_increase_per_update, update_interval,
                           use_market_maker_rate, initial_buying_rate, final_buying_rate):
        validate_load_device_price(fit_to_limit=fit_to_limit,
                                   energy_rate_increase_per_update=energy_rate_increase_per_update)

        if update_interval is None:
            update_interval = \
                duration(minutes=ConstSettings.GeneralSettings.DEFAULT_UPDATE_INTERVAL)

        self.use_market_maker_rate = use_market_maker_rate

        if isinstance(update_interval, int):
            update_interval = duration(minutes=update_interval)

        BidEnabledStrategy.__init__(self)
        self.bid_update = \
            UpdateFrequencyMixin(initial_rate=initial_buying_rate,
                                 final_rate=final_buying_rate,
                                 fit_to_limit=fit_to_limit,
                                 energy_rate_change_per_update=energy_rate_increase_per_update,
                                 update_interval=update_interval, rate_limit_object=min)
        self.fit_to_limit = fit_to_limit

    def _validate_rates(self):
        for time_slot in generate_market_slot_list():
            rate_change = None if self.fit_to_limit else \
                self.bid_update.energy_rate_change_per_update[time_slot]
            validate_load_device_price(
                initial_buying_rate=self.bid_update.initial_rate[time_slot],
                energy_rate_increase_per_update=rate_change,
                final_buying_rate=self.bid_update.final_rate[time_slot],
                fit_to_limit=self.bid_update.fit_to_limit)

    def event_activate(self):
        self._calculate_active_markets()
        self.event_activate_price()
        self.event_activate_energy()

    def event_market_cycle(self):
        super().event_market_cycle()
        self._calculate_active_markets()
        for market in self.active_markets:
            current_day = self._get_day_of_timestamp(market.time_slot)
            if self.hrs_per_day[current_day] <= FLOATING_POINT_TOLERANCE:
                self.energy_requirement_Wh[market.time_slot] = 0.0
                self.state.desired_energy_Wh[market.time_slot] = 0.0
        self.event_market_cycle_prices()
        if self.area.current_market:
            self.state.total_energy_demanded_wh += \
                self.state.desired_energy_Wh[self.area.current_market.time_slot]
        else:
            self.state.total_energy_demanded_wh = 0.0
        self._delete_past_state()

    def _delete_past_state(self):
        if ConstSettings.GeneralSettings.KEEP_PAST_MARKETS is True or \
                self.area.current_market is None:
            return
        to_delete = []
        for k in self.energy_requirement_Wh.keys():
            if k < self.area.current_market.time_slot:
                to_delete.append(k)
        for k in to_delete:
            del self.energy_requirement_Wh[k]
            del self.state.desired_energy_Wh[k]

    def _area_reconfigure_prices(self, **kwargs):
        if key_in_dict_and_not_none(kwargs, 'initial_buying_rate'):
            self.bid_update.initial_rate = read_arbitrary_profile(InputProfileTypes.IDENTITY,
                                                                  kwargs['initial_buying_rate'])
        if key_in_dict_and_not_none(kwargs, 'final_buying_rate'):
            self.bid_update.final_rate = read_arbitrary_profile(InputProfileTypes.IDENTITY,
                                                                kwargs['final_buying_rate'])
        if key_in_dict_and_not_none(kwargs, 'energy_rate_increase_per_update'):
            self.bid_update.energy_rate_change_per_update = \
                read_arbitrary_profile(InputProfileTypes.IDENTITY,
                                       kwargs['energy_rate_increase_per_update'])
        if key_in_dict_and_not_none(kwargs, 'fit_to_limit'):
            self.bid_update.fit_to_limit = kwargs['fit_to_limit']
        if key_in_dict_and_not_none(kwargs, 'update_interval'):
            if isinstance(kwargs['update_interval'], int):
                update_interval = duration(minutes=kwargs['update_interval'])
            else:
                update_interval = kwargs['update_interval']
            self.bid_update.update_interval = update_interval
        if key_in_dict_and_not_none(kwargs, 'use_market_maker_rate'):
            self.use_market_maker_rate = ['use_market_maker_rate']

        self._validate_rates()

    def area_reconfigure_event(self, **kwargs):
        if key_in_dict_and_not_none(kwargs, 'hrs_per_day') or \
                key_in_dict_and_not_none(kwargs, 'hrs_of_day'):
            self.assign_hours_of_per_day(kwargs['hrs_of_day'], kwargs['hrs_per_day'])
            self.hrs_per_day = {day: self._initial_hrs_per_day
                                for day in range(self.area.config.sim_duration.days + 1)}
        if key_in_dict_and_not_none(kwargs, 'avg_power_W'):
            self.avg_power_W = ['avg_power_W']
            self.assign_energy_requirement(kwargs['avg_power_W'])

        self._area_reconfigure_prices(**kwargs)

    def event_activate_price(self):
        # If use_market_maker_rate is true, overwrite final_buying_rate to market maker rate
        if self.use_market_maker_rate:
            self.area_reconfigure_event(final_buying_rate=GlobalConfig.market_maker_rate)
        self._validate_rates()
        self.bid_update.update_on_activate()
        self._set_alternative_pricing_scheme()

    def _find_acceptable_offer(self, market):
        offers = market.most_affordable_offers
        return random.choice(offers)

    def _one_sided_market_event_tick(self, market, offer=None):
        try:
            if offer is None:
                if not market.offers:
                    return
                acceptable_offer = self._find_acceptable_offer(market)
            else:
                if offer.id not in market.offers:
                    return
                acceptable_offer = offer
            current_day = self._get_day_of_timestamp(market.time_slot)
            if acceptable_offer and \
                    self.hrs_per_day[current_day] > FLOATING_POINT_TOLERANCE and \
                    round(acceptable_offer.energy_rate, 8) <= \
                    self.bid_update.final_rate[market.time_slot]:
                max_energy = self.energy_requirement_Wh[market.time_slot] / 1000.0
                if max_energy < FLOATING_POINT_TOLERANCE:
                    return
                if acceptable_offer.energy > max_energy:
                    self.energy_requirement_Wh[market.time_slot] = 0
                    self.accept_offer(market, acceptable_offer, energy=max_energy,
                                      buyer_origin=self.owner.name)
                    self.hrs_per_day[current_day] -= self._operating_hours(max_energy)
                else:
                    self.energy_requirement_Wh[market.time_slot] -= \
                        acceptable_offer.energy * 1000.0
                    self.accept_offer(market, acceptable_offer, buyer_origin=self.owner.name)
                    self.hrs_per_day[current_day] -= self._operating_hours(acceptable_offer.energy)

                assert self.energy_requirement_Wh[market.time_slot] >= -FLOATING_POINT_TOLERANCE, \
                    f"Energy requirement for load {self.owner.name} fell below zero " \
                    f"({self.energy_requirement_Wh[market.time_slot]})."

        except MarketException:
            self.log.exception("An Error occurred while buying an offer")

    def _double_sided_market_event_tick(self, market):
        self.bid_update.update_posted_bids_over_ticks(market, self)

    def event_tick(self):
        for market in self.active_markets:
            if market.time_slot not in self.energy_requirement_Wh:
                continue
            if self.energy_requirement_Wh[market.time_slot] <= FLOATING_POINT_TOLERANCE:
                continue

            if ConstSettings.IAASettings.MARKET_TYPE == 1:
                self._one_sided_market_event_tick(market)
            elif ConstSettings.IAASettings.MARKET_TYPE == 2 or \
                    ConstSettings.IAASettings.MARKET_TYPE == 3:
                self._double_sided_market_event_tick(market)

        self.bid_update.increment_update_counter_all_markets(self)

    def event_offer(self, *, market_id, offer):
        super().event_offer(market_id=market_id, offer=offer)
        market = self.area.get_future_market_from_id(market_id)
        if market.time_slot in self.energy_requirement_Wh and \
                self._is_market_active(market) and \
                self.energy_requirement_Wh[market.time_slot] > FLOATING_POINT_TOLERANCE and \
                offer.seller != self.owner.name and \
                offer.seller != self.area.name:
            if ConstSettings.IAASettings.MARKET_TYPE == 1:
                self._one_sided_market_event_tick(market, offer)

    def _set_alternative_pricing_scheme(self):
        if ConstSettings.IAASettings.AlternativePricing.PRICING_SCHEME != 0:
            for time_slot in generate_market_slot_list():
                final_rate = self.area.config.market_maker_rate[time_slot]
                self.bid_update.reassign_mixin_arguments(time_slot, initial_rate=0,
                                                         final_rate=final_rate)

    def event_market_cycle_prices(self):
        if ConstSettings.IAASettings.MARKET_TYPE == 1:
            return
        for market in self.active_markets:
            if self.energy_requirement_Wh[market.time_slot] > 0:
                if self.is_eligible_for_balancing_market:
                    bid_energy = \
                        self.energy_requirement_Wh[market.time_slot] - \
                        self.balancing_energy_ratio.demand * \
                        self.state.desired_energy_Wh[market.time_slot]
                else:
                    bid_energy = self.energy_requirement_Wh[market.time_slot]
                if not self.are_bids_posted(market.id):
                    self.post_first_bid(market, bid_energy)
                else:
                    self.bid_update.update_market_cycle_bids(self)

    def event_balancing_market_cycle(self):
        for market in self.active_markets:
            self._demand_balancing_offer(market)

    def event_bid_traded(self, *, market_id, bid_trade):
        super().event_bid_traded(market_id=market_id, bid_trade=bid_trade)
        market = self.area.get_future_market_from_id(market_id)

        if bid_trade.offer.buyer == self.owner.name:
            self.energy_requirement_Wh[market.time_slot] -= bid_trade.offer.energy * 1000.0
            self.hrs_per_day[self._get_day_of_timestamp(market.time_slot)] -= \
                self._operating_hours(bid_trade.offer.energy)
            assert self.energy_requirement_Wh[market.time_slot] >= -FLOATING_POINT_TOLERANCE, \
                f"Energy requirement for load {self.owner.name} fell below zero " \
                f"({self.energy_requirement_Wh[market.time_slot]})."

    def event_trade(self, *, market_id, trade):
        market = self.area.get_future_market_from_id(market_id)
        assert market is not None

        self.assert_if_trade_bid_price_is_too_high(market, trade)

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

    def event_activate_energy(self):
        self.hrs_per_day = {day: self._initial_hrs_per_day
                            for day in range(self.area.config.sim_duration.days + 1)}
        self._simulation_start_timestamp = self.area.now
        self.assign_energy_requirement(self.avg_power_W)

    @property
    def active_markets(self):
        return self._active_markets

    def _calculate_active_markets(self):
        self._active_markets = [
            market for market in self.area.all_markets
            if self._is_market_active(market)
        ] if self.area else []

    def _is_market_active(self, market):
        return self._allowed_operating_hours(market.time_slot) and \
            market.in_sim_duration and \
            (not self.area.current_market or
             market.time_slot >= self.area.current_market.time_slot)

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
        for slot_time in generate_market_slot_list(area=self.area):
            if self._allowed_operating_hours(slot_time) and slot_time >= self.area.now:
                self.energy_requirement_Wh[slot_time] = self.energy_per_slot_Wh
                self.state.desired_energy_Wh[slot_time] = self.energy_per_slot_Wh

    def _allowed_operating_hours(self, time):
        return time.hour in self.hrs_of_day

    def _operating_hours(self, energy):
        return (((energy * 1000) / self.energy_per_slot_Wh)
                * (self.area.config.slot_length / duration(hours=1)))

    def _get_day_of_timestamp(self, time_slot):
        return (time_slot - self._simulation_start_timestamp).days


class CellTowerLoadHoursStrategy(LoadHoursStrategy):
    pass
