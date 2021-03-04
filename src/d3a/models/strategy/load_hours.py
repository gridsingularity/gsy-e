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
import traceback
from numpy import random
from logging import getLogger
from pendulum import duration, DateTime  # NOQA
from typing import Union, Dict  # NOQA
from collections import namedtuple

from d3a.d3a_core.util import find_object_of_same_weekday_and_time, convert_W_to_Wh
from d3a.d3a_core.exceptions import MarketException
from d3a.models.state import LoadState
from d3a.models.strategy import BidEnabledStrategy
from d3a_interface.constants_limits import ConstSettings
from d3a_interface.device_validator import validate_load_device_price, validate_load_device_energy
from d3a.models.strategy.update_frequency import UpdateFrequencyMixin
from d3a.d3a_core.device_registry import DeviceRegistry
from d3a.models.read_user_profile import read_arbitrary_profile
from d3a.models.read_user_profile import InputProfileTypes
from d3a.constants import FLOATING_POINT_TOLERANCE, DEFAULT_PRECISION
from d3a_interface.constants_limits import GlobalConfig
from d3a_interface.utils import key_in_dict_and_not_none
from d3a import constants

log = getLogger(__name__)

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
        self.hrs_per_day = {}  # type: Dict[int, int]

        self.assign_hours_of_per_day(hrs_of_day, hrs_per_day)
        self.balancing_energy_ratio = BalancingRatio(*balancing_energy_ratio)

        self._init_price_update(fit_to_limit, energy_rate_increase_per_update, update_interval,
                                use_market_maker_rate, initial_buying_rate, final_buying_rate)
        self._calculate_active_markets()
        self._cycled_market = set()
        self._simulation_start_timestamp = None

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

    @staticmethod
    def _validate_rates(initial_rate, final_rate, energy_rate_change_per_update,
                        fit_to_limit):
        # all parameters have to be validated for each time slot here
        for time_slot in initial_rate.keys():
            rate_change = None if fit_to_limit else \
                find_object_of_same_weekday_and_time(energy_rate_change_per_update, time_slot)
            validate_load_device_price(
                initial_buying_rate=initial_rate[time_slot],
                energy_rate_increase_per_update=rate_change,
                final_buying_rate=find_object_of_same_weekday_and_time(final_rate, time_slot),
                fit_to_limit=fit_to_limit)

    def event_activate(self, **kwargs):
        self._calculate_active_markets()
        self.event_activate_price()
        self.bid_update.update_and_populate_price_settings(self.area)
        self.event_activate_energy()

    def event_market_cycle(self):
        super().event_market_cycle()
        self.add_entry_in_hrs_per_day()
        self.bid_update.update_and_populate_price_settings(self.area)
        self._calculate_active_markets()
        self._update_energy_requirement_future_markets()
        self._set_alternative_pricing_scheme()
        self.update_state()

    def add_entry_in_hrs_per_day(self, overwrite=False):
        for market in self.area.all_markets:
            current_day = self._get_day_of_timestamp(market.time_slot)
            if current_day not in self.hrs_per_day or overwrite:
                self.hrs_per_day[current_day] = self._initial_hrs_per_day

    def update_state(self):
        self.post_or_update_bid()
        if self.area.current_market:
            self._cycled_market.add(self.area.current_market.time_slot)
        self._delete_past_state()

    def _delete_past_state(self):
        if constants.D3A_TEST_RUN is True or \
                self.area.current_market is None:
            return

        self.state.delete_past_state_values(self.area.current_market.time_slot)
        self.bid_update.delete_past_state_values(self.area.current_market.time_slot)

    def _area_reconfigure_prices(self, **kwargs):
        if key_in_dict_and_not_none(kwargs, 'initial_buying_rate'):
            initial_rate = read_arbitrary_profile(InputProfileTypes.IDENTITY,
                                                  kwargs['initial_buying_rate'])
        else:
            initial_rate = self.bid_update.initial_rate_profile_buffer
        if key_in_dict_and_not_none(kwargs, 'final_buying_rate'):
            final_rate = read_arbitrary_profile(InputProfileTypes.IDENTITY,
                                                kwargs['final_buying_rate'])
        else:
            final_rate = self.bid_update.final_rate_profile_buffer
        if key_in_dict_and_not_none(kwargs, 'energy_rate_increase_per_update'):
            energy_rate_change_per_update = \
                read_arbitrary_profile(InputProfileTypes.IDENTITY,
                                       kwargs['energy_rate_increase_per_update'])
        else:
            energy_rate_change_per_update = \
                self.bid_update.energy_rate_change_per_update_profile_buffer
        if key_in_dict_and_not_none(kwargs, 'fit_to_limit'):
            fit_to_limit = kwargs['fit_to_limit']
        else:
            fit_to_limit = self.bid_update.fit_to_limit
        if key_in_dict_and_not_none(kwargs, 'update_interval'):
            if isinstance(kwargs['update_interval'], int):
                update_interval = duration(minutes=kwargs['update_interval'])
            else:
                update_interval = kwargs['update_interval']
        else:
            update_interval = self.bid_update.update_interval

        if key_in_dict_and_not_none(kwargs, 'use_market_maker_rate'):
            self.use_market_maker_rate = kwargs['use_market_maker_rate']

        try:
            self._validate_rates(initial_rate, final_rate, energy_rate_change_per_update,
                                 fit_to_limit)
        except Exception as e:
            log.error(f"LoadHours._area_reconfigure_prices failed. Exception: {e}. "
                      f"Traceback: {traceback.format_exc()}")
            return

        self.bid_update.initial_rate_profile_buffer = initial_rate
        self.bid_update.final_rate_profile_buffer = final_rate
        self.bid_update.energy_rate_change_per_update_profile_buffer = \
            energy_rate_change_per_update
        self.bid_update.fit_to_limit = fit_to_limit
        self.bid_update.update_interval = update_interval

    def area_reconfigure_event(self, **kwargs):
        if key_in_dict_and_not_none(kwargs, 'hrs_per_day') or \
                key_in_dict_and_not_none(kwargs, 'hrs_of_day'):
            self.assign_hours_of_per_day(kwargs['hrs_of_day'], kwargs['hrs_per_day'])
            self.add_entry_in_hrs_per_day(overwrite=True)
        if key_in_dict_and_not_none(kwargs, 'avg_power_W'):
            self.avg_power_W = kwargs['avg_power_W']
            self._update_energy_requirement_future_markets()
        self._area_reconfigure_prices(**kwargs)
        self.bid_update.update_and_populate_price_settings(self.area)

    def event_activate_price(self):
        # If use_market_maker_rate is true, overwrite final_buying_rate to market maker rate
        if self.use_market_maker_rate:
            if isinstance(GlobalConfig.market_maker_rate, dict):
                self.area_reconfigure_event(final_buying_rate=GlobalConfig.market_maker_rate.get(
                    self.owner.parent.next_market.time_slot, 0) +
                        self.owner.get_path_to_root_fees())
            else:
                self.area_reconfigure_event(final_buying_rate=GlobalConfig.market_maker_rate +
                                            self.owner.get_path_to_root_fees())
        self._validate_rates(self.bid_update.initial_rate_profile_buffer,
                             self.bid_update.final_rate_profile_buffer,
                             self.bid_update.energy_rate_change_per_update_profile_buffer,
                             self.bid_update.fit_to_limit)

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
            time_slot = market.time_slot
            current_day = self._get_day_of_timestamp(time_slot)
            if acceptable_offer and \
                    self.hrs_per_day[current_day] > FLOATING_POINT_TOLERANCE and \
                    round(acceptable_offer.energy_rate, DEFAULT_PRECISION) <= \
                    self.bid_update.final_rate[time_slot] + FLOATING_POINT_TOLERANCE:

                if not self.state.can_buy_more_energy(time_slot):
                    return

                energy_Wh = self.state.calculate_energy_to_accept(
                    acceptable_offer.energy * 1000.0, time_slot)
                self.accept_offer(market, acceptable_offer, energy=energy_Wh / 1000.0,
                                  buyer_origin=self.owner.name,
                                  buyer_origin_id=self.owner.uuid,
                                  buyer_id=self.owner.uuid)
                self.state.decrement_energy_requirement(energy_Wh, time_slot, self.owner.name)
                self.hrs_per_day[current_day] -= self._operating_hours(energy_Wh / 1000.0)

        except MarketException:
            self.log.exception("An Error occurred while buying an offer")

    def _double_sided_market_event_tick(self, market):
        self.bid_update.update_posted_bids_over_ticks(market, self)

    def event_tick(self):
        for market in self.active_markets:
            if not self.state.can_buy_more_energy(market.time_slot):
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
        # TODO: do we really need self._cycled_market ?
        if market.time_slot not in self._cycled_market:
            return
        if self._is_market_active(market) and \
                self.state.can_buy_more_energy(market.time_slot) and \
                offer.seller != self.owner.name and \
                offer.seller != self.area.name:
            if ConstSettings.IAASettings.MARKET_TYPE == 1:
                self._one_sided_market_event_tick(market, offer)

    def _set_alternative_pricing_scheme(self):
        if ConstSettings.IAASettings.AlternativePricing.PRICING_SCHEME != 0:
            for market in self.area.all_markets:
                time_slot = market.time_slot
                final_rate = self.area.config.market_maker_rate[time_slot]
                self.bid_update.reassign_mixin_arguments(time_slot, initial_rate=0,
                                                         final_rate=final_rate)

    def post_or_update_bid(self):
        if ConstSettings.IAASettings.MARKET_TYPE == 1:
            return
        for market in self.active_markets:
            if self.state.can_buy_more_energy(market.time_slot):
                bid_energy = self.state.calculate_energy_to_bid(market.time_slot)
                if self.is_eligible_for_balancing_market:
                    bid_energy -= self.state.get_desired_energy(market.time_slot) * \
                                  self.balancing_energy_ratio.demand
                try:
                    if not self.are_bids_posted(market.id):
                        self.post_first_bid(market, bid_energy)
                    else:
                        self.bid_update.update_market_cycle_bids(self)
                except MarketException:
                    pass

    def event_balancing_market_cycle(self):
        for market in self.active_markets:
            self._demand_balancing_offer(market)

    def event_bid_traded(self, *, market_id, bid_trade):
        super().event_bid_traded(market_id=market_id, bid_trade=bid_trade)
        market = self.area.get_future_market_from_id(market_id)

        if bid_trade.offer.buyer == self.owner.name:
            self.state.decrement_energy_requirement(
                bid_trade.offer.energy * 1000,
                market.time_slot, self.owner.name)
            market_day = self._get_day_of_timestamp(market.time_slot)
            if self.hrs_per_day != {} and market_day in self.hrs_per_day:
                self.hrs_per_day[market_day] -= self._operating_hours(bid_trade.offer.energy)

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
            self.state.get_desired_energy_Wh(market.time_slot)
        self.state.decrement_energy_requirement(ramp_up_energy, market.time_slot, self.owner.name)
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
        self.hrs_per_day = {0: self._initial_hrs_per_day}
        self._simulation_start_timestamp = self.area.now
        self._update_energy_requirement_future_markets()

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

    def _update_energy_requirement_future_markets(self):
        self.energy_per_slot_Wh = convert_W_to_Wh(self.avg_power_W, self.area.config.slot_length)
        for market in self.area.all_markets:
            desired_energy_Wh = self.energy_per_slot_Wh \
                if self._allowed_operating_hours(market.time_slot) else 0.0
            self.state.set_desired_energy(desired_energy_Wh, market.time_slot)

        for market in self.active_markets:
            current_day = self._get_day_of_timestamp(market.time_slot)
            if current_day not in self.hrs_per_day or \
                    self.hrs_per_day[current_day] <= FLOATING_POINT_TOLERANCE:
                # Overwrite desired energy to 0 in case the previous step has populated the
                # desired energy by the hrs_per_day have been exhausted.
                self.state.set_desired_energy(0.0, market.time_slot, True)
        if self.area.current_market:
            self.state.update_total_demanded_energy(self.area.current_market.time_slot)

    def _allowed_operating_hours(self, time):
        return time.hour in self.hrs_of_day

    def _operating_hours(self, energy_kWh):
        return (((energy_kWh * 1000) / self.energy_per_slot_Wh)
                * (self.area.config.slot_length / duration(hours=1)))

    def _get_day_of_timestamp(self, time_slot):
        if self._simulation_start_timestamp is None:
            return 0
        return (time_slot - self._simulation_start_timestamp).days
