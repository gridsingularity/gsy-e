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
import math
from typing import Dict  # noqa
from pendulum import Time  # noqa
from pendulum import duration
from logging import getLogger

from d3a.d3a_core.util import find_object_of_same_weekday_and_time, convert_W_to_kWh
from d3a.models.strategy import BaseStrategy
from d3a_interface.constants_limits import ConstSettings
from d3a_interface.device_validator import validate_pv_device_energy, validate_pv_device_price
from d3a.models.strategy.update_frequency import UpdateFrequencyMixin
from d3a.models.state import PVState
from d3a.d3a_core.exceptions import MarketException
from d3a.models.read_user_profile import read_arbitrary_profile, InputProfileTypes
from d3a_interface.constants_limits import GlobalConfig
from d3a_interface.utils import key_in_dict_and_not_none
from d3a import constants

log = getLogger(__name__)


class PVStrategy(BaseStrategy):

    parameters = ('panel_count', 'initial_selling_rate', 'final_selling_rate',
                  'fit_to_limit', 'update_interval', 'energy_rate_decrease_per_update',
                  'max_panel_power_W', 'use_market_maker_rate')

    def __init__(self, panel_count: int = 1,
                 initial_selling_rate:
                 float = ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE,
                 final_selling_rate:
                 float = ConstSettings.PVSettings.SELLING_RATE_RANGE.final,
                 fit_to_limit: bool = True,
                 update_interval=None,
                 energy_rate_decrease_per_update=None,
                 max_panel_power_W: float = None,
                 use_market_maker_rate: bool = False):
        """
        :param panel_count: Number of solar panels for this PV plant
        :param initial_selling_rate: Upper Threshold for PV offers
        :param final_selling_rate: Lower Threshold for PV offers
        :param fit_to_limit: Linear curve following initial_selling_rate & initial_selling_rate
        :param update_interval: Interval after which PV will update its offer
        :param energy_rate_decrease_per_update: Slope of PV Offer change per update
        :param max_panel_power_W:
        """
        super().__init__()
        validate_pv_device_energy(panel_count=panel_count, max_panel_power_W=max_panel_power_W)

        self.panel_count = panel_count
        self.max_panel_power_W = max_panel_power_W
        self.state = PVState()

        self._init_price_update(update_interval, initial_selling_rate, final_selling_rate,
                                use_market_maker_rate, fit_to_limit,
                                energy_rate_decrease_per_update)

    def _init_price_update(self, update_interval, initial_selling_rate, final_selling_rate,
                           use_market_maker_rate, fit_to_limit, energy_rate_decrease_per_update):
        if update_interval is None:
            update_interval = \
                duration(minutes=ConstSettings.GeneralSettings.DEFAULT_UPDATE_INTERVAL)

        if isinstance(update_interval, int):
            update_interval = duration(minutes=update_interval)

        self.final_selling_rate = final_selling_rate
        self.use_market_maker_rate = use_market_maker_rate
        validate_pv_device_price(fit_to_limit=fit_to_limit,
                                 energy_rate_decrease_per_update=energy_rate_decrease_per_update)

        self.offer_update = UpdateFrequencyMixin(initial_selling_rate, final_selling_rate,
                                                 fit_to_limit, energy_rate_decrease_per_update,
                                                 update_interval)

    def area_reconfigure_event(self, **kwargs):
        self._area_reconfigure_prices(**kwargs)
        self.offer_update.update_and_populate_price_settings(self.area)

        if key_in_dict_and_not_none(kwargs, 'panel_count'):
            self.panel_count = kwargs['panel_count']
        if key_in_dict_and_not_none(kwargs, 'max_panel_power_W'):
            self.max_panel_power_W = kwargs['max_panel_power_W']

        self.set_produced_energy_forecast_kWh_future_markets(reconfigure=True)

    def _area_reconfigure_prices(self, **kwargs):
        if key_in_dict_and_not_none(kwargs, 'initial_selling_rate'):
            initial_rate = read_arbitrary_profile(InputProfileTypes.IDENTITY,
                                                  kwargs['initial_selling_rate'])
        else:
            initial_rate = self.offer_update.initial_rate_profile_buffer

        if key_in_dict_and_not_none(kwargs, 'final_selling_rate'):
            final_rate = read_arbitrary_profile(InputProfileTypes.IDENTITY,
                                                kwargs['final_selling_rate'])
        else:
            final_rate = self.offer_update.final_rate_profile_buffer
        if key_in_dict_and_not_none(kwargs, 'energy_rate_decrease_per_update'):
            energy_rate_change_per_update = \
                read_arbitrary_profile(InputProfileTypes.IDENTITY,
                                       kwargs['energy_rate_decrease_per_update'])
        else:
            energy_rate_change_per_update = \
                self.offer_update.energy_rate_change_per_update_profile_buffer
        if key_in_dict_and_not_none(kwargs, 'fit_to_limit'):
            fit_to_limit = kwargs['fit_to_limit']
        else:
            fit_to_limit = self.offer_update.fit_to_limit
        if key_in_dict_and_not_none(kwargs, 'update_interval'):
            if isinstance(kwargs['update_interval'], int):
                update_interval = duration(minutes=kwargs['update_interval'])
            else:
                update_interval = kwargs['update_interval']
        else:
            update_interval = self.offer_update.update_interval
        if key_in_dict_and_not_none(kwargs, 'use_market_maker_rate'):
            self.use_market_maker_rate = kwargs['use_market_maker_rate']

        try:
            self._validate_rates(initial_rate, final_rate, energy_rate_change_per_update,
                                 fit_to_limit)
        except Exception as e:
            log.error(f"PVStrategy._area_reconfigure_prices failed. Exception: {e}. "
                      f"Traceback: {traceback.format_exc()}")
            return

        self.offer_update.initial_rate_profile_buffer = initial_rate
        self.offer_update.final_rate_profile_buffer = final_rate
        self.offer_update.energy_rate_change_per_update_profile_buffer = \
            energy_rate_change_per_update
        self.offer_update.fit_to_limit = fit_to_limit
        self.offer_update.update_interval = update_interval

    @staticmethod
    def _validate_rates(initial_rate, final_rate, energy_rate_change_per_update, fit_to_limit):
        # all parameters have to be validated for each time slot here
        for time_slot in initial_rate.keys():
            rate_change = None if fit_to_limit else \
                find_object_of_same_weekday_and_time(energy_rate_change_per_update, time_slot)
            validate_pv_device_price(
                initial_selling_rate=initial_rate[time_slot],
                final_selling_rate=find_object_of_same_weekday_and_time(final_rate, time_slot),
                energy_rate_decrease_per_update=rate_change,
                fit_to_limit=fit_to_limit)

    def event_activate(self, **kwargs):
        self.event_activate_price()
        self.event_activate_energy()
        self.offer_update.update_and_populate_price_settings(self.area)

    def event_activate_price(self):
        # If use_market_maker_rate is true, overwrite initial_selling_rate to market maker rate
        if self.use_market_maker_rate:
            if isinstance(GlobalConfig.market_maker_rate, dict):
                self._area_reconfigure_prices(
                    initial_selling_rate=find_object_of_same_weekday_and_time(
                        GlobalConfig.market_maker_rate, self.owner.parent.next_market.time_slot
                    ) - self.owner.get_path_to_root_fees(),
                    validate=False)
            else:
                self._area_reconfigure_prices(initial_selling_rate=GlobalConfig.market_maker_rate -
                                              self.owner.get_path_to_root_fees(), validate=False)
        self._validate_rates(self.offer_update.initial_rate_profile_buffer,
                             self.offer_update.final_rate_profile_buffer,
                             self.offer_update.energy_rate_change_per_update_profile_buffer,
                             self.offer_update.fit_to_limit)

    def event_activate_energy(self):
        if self.max_panel_power_W is None:
            self.max_panel_power_W = self.area.config.max_panel_power_W
        self.set_produced_energy_forecast_kWh_future_markets(reconfigure=True)

    def event_tick(self):
        self.offer_update.update_offer(self)
        self.offer_update.increment_update_counter_all_markets(self)

    def set_produced_energy_forecast_kWh_future_markets(self, reconfigure=True):
        # This forecast ist based on the real PV system data provided by enphase
        # They can be found in the tools folder
        # A fit of a gaussian function to those data results in a formula Energy(time)
        for market in self.area.all_markets:
            slot_time = market.time_slot
            difference_to_midnight_in_minutes = \
                slot_time.diff(self.area.now.start_of("day")).in_minutes() % (60 * 24)
            available_energy_kWh = self.gaussian_energy_forecast_kWh(
                difference_to_midnight_in_minutes) * self.panel_count
            self.state.set_available_energy(available_energy_kWh, slot_time, reconfigure)

    def gaussian_energy_forecast_kWh(self, time_in_minutes=0):
        # The sun rises at approx 6:30 and sets at 18hr
        # time_in_minutes is the difference in time to midnight

        # Clamp to day range
        time_in_minutes %= 60 * 24

        if (8 * 60) > time_in_minutes or time_in_minutes > (16.5 * 60):
            gauss_forecast = 0

        else:
            gauss_forecast = self.max_panel_power_W * math.exp(
                # time/5 is needed because we only have one data set per 5 minutes

                (- (((round(time_in_minutes / 5, 0)) - 147.2)
                    / 38.60) ** 2
                 )
            )
        return round(convert_W_to_kWh(gauss_forecast, self.area.config.slot_length), 4)

    def event_market_cycle(self):
        super().event_market_cycle()
        self.set_produced_energy_forecast_kWh_future_markets(reconfigure=False)
        self._set_alternative_pricing_scheme()
        self.event_market_cycle_price()
        self._delete_past_state()

    def _delete_past_state(self):
        if constants.D3A_TEST_RUN is True or \
                self.area.current_market is None:
            return

        self.state.delete_past_state(self.area.current_market.time_slot)
        self.offer_update.delete_past_state_values(self.area.current_market.time_slot)

    def event_market_cycle_price(self):
        self.offer_update.update_and_populate_price_settings(self.area)
        self.offer_update.update_market_cycle_offers(self)

        # Iterate over all markets open in the future
        for market in self.area.all_markets:
            offer_energy_kWh = self.state.get_available_energy_kWh(market.time_slot)
            # We need to subtract the energy from the offers that are already posted in this
            # market in order to validate that more offers need to be posted.
            offer_energy_kWh -= self.offers.open_offer_energy(market.id)
            if offer_energy_kWh > 0:
                offer_price = \
                    self.offer_update.initial_rate[market.time_slot] * offer_energy_kWh
                try:
                    offer = market.offer(
                        offer_price,
                        offer_energy_kWh,
                        self.owner.name,
                        original_offer_price=offer_price,
                        seller_origin=self.owner.name,
                        seller_origin_id=self.owner.uuid,
                        seller_id=self.owner.uuid
                    )
                    self.offers.post(offer, market.id)
                except MarketException:
                    pass

    def event_trade(self, *, market_id, trade):
        super().event_trade(market_id=market_id, trade=trade)
        market = self.area.get_future_market_from_id(market_id)
        if market is None:
            return

        self.assert_if_trade_offer_price_is_too_low(market_id, trade)

        if trade.seller == self.owner.name:
            self.state.decrement_available_energy(
                trade.offer.energy, market.time_slot, self.owner.name)

    def _set_alternative_pricing_scheme(self):
        if ConstSettings.IAASettings.AlternativePricing.PRICING_SCHEME != 0:
            for market in self.area.all_markets:
                time_slot = market.time_slot
                if ConstSettings.IAASettings.AlternativePricing.PRICING_SCHEME == 1:
                    self.offer_update.reassign_mixin_arguments(time_slot, initial_rate=0,
                                                               final_rate=0)
                elif ConstSettings.IAASettings.AlternativePricing.PRICING_SCHEME == 2:
                    rate = \
                        self.area.config.market_maker_rate[time_slot] * \
                        ConstSettings.IAASettings.AlternativePricing.FEED_IN_TARIFF_PERCENTAGE / \
                        100
                    self.offer_update.reassign_mixin_arguments(time_slot, initial_rate=rate,
                                                               final_rate=rate)
                elif ConstSettings.IAASettings.AlternativePricing.PRICING_SCHEME == 3:
                    rate = self.area.config.market_maker_rate[time_slot]
                    self.offer_update.reassign_mixin_arguments(time_slot, initial_rate=rate,
                                                               final_rate=rate)
                else:
                    raise MarketException
