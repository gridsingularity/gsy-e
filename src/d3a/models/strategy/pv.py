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
from typing import Dict  # noqa
from pendulum import Time  # noqa
import math
from pendulum import duration

from d3a.d3a_core.util import generate_market_slot_list
from d3a.models.strategy import BaseStrategy
from d3a_interface.constants_limits import ConstSettings
from d3a_interface.device_validator import validate_pv_device_energy, validate_pv_device_price
from d3a.models.strategy.update_frequency import UpdateFrequencyMixin
from d3a.models.state import PVState
from d3a.constants import FLOATING_POINT_TOLERANCE
from d3a.d3a_core.exceptions import MarketException
from d3a.models.read_user_profile import read_arbitrary_profile, InputProfileTypes
from d3a_interface.constants_limits import GlobalConfig
from d3a.models.strategy import assert_if_trade_offer_price_is_too_low


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
        self.energy_production_forecast_kWh = {}  # type: Dict[Time, float]
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

    def area_reconfigure_event(self, validate=True, **kwargs):
        assert all(k in self.parameters for k in kwargs.keys())
        self._area_reconfigure_prices(validate, **kwargs)

        validate_pv_device_energy(**kwargs)
        self.produced_energy_forecast_kWh()
        for name, value in kwargs.items():
            setattr(self, name, value)

    def _area_reconfigure_prices(self, validate=True, **kwargs):
        if validate:
            validate_pv_device_price(**kwargs)

        if 'initial_selling_rate' in kwargs and kwargs['initial_selling_rate'] is not None:
            self.offer_update.initial_rate = read_arbitrary_profile(InputProfileTypes.IDENTITY,
                                                                    kwargs['initial_selling_rate'])
        if 'final_selling_rate' in kwargs and kwargs['final_selling_rate'] is not None:
            self.offer_update.final_rate = read_arbitrary_profile(InputProfileTypes.IDENTITY,
                                                                  kwargs['final_selling_rate'])

        self._validate_rates()
        self.offer_update.update_offer(self)

    def _validate_rates(self):
        for time_slot in generate_market_slot_list():
            validate_pv_device_price(
                initial_selling_rate=self.offer_update.initial_rate[time_slot],
                final_selling_rate=self.offer_update.final_rate[time_slot])

    def event_activate(self):
        self.event_activate_price()
        self.event_activate_energy()

    def event_activate_price(self):
        # If use_market_maker_rate is true, overwrite initial_selling_rate to market maker rate
        if self.use_market_maker_rate:
            self.area_reconfigure_event(initial_selling_rate=GlobalConfig.market_maker_rate,
                                        validate=False)
        self._validate_rates()
        # Calculating the produced energy
        self._set_alternative_pricing_scheme()
        self.offer_update.update_on_activate()

    def event_activate_energy(self):
        if self.max_panel_power_W is None:
            self.max_panel_power_W = self.area.config.max_panel_power_W
        self.produced_energy_forecast_kWh()

    def event_tick(self):
        self.offer_update.update_offer(self)
        self.offer_update.increment_update_counter_all_markets(self)

    def produced_energy_forecast_kWh(self):
        # This forecast ist based on the real PV system data provided by enphase
        # They can be found in the tools folder
        # A fit of a gaussian function to those data results in a formula Energy(time)
        for slot_time in generate_market_slot_list(area=self.area):
            if slot_time >= self.area.now:
                difference_to_midnight_in_minutes = \
                    slot_time.diff(self.area.now.start_of("day")).in_minutes() % (60 * 24)
                self.energy_production_forecast_kWh[slot_time] = \
                    self.gaussian_energy_forecast_kWh(
                        difference_to_midnight_in_minutes) * self.panel_count
                self.state.available_energy_kWh[slot_time] = \
                    self.energy_production_forecast_kWh[slot_time]
                assert self.energy_production_forecast_kWh[slot_time] >= 0.0

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
        # /1000 is needed to convert Wh into kWh
        w_to_wh_factor = (self.area.config.slot_length / duration(hours=1))
        return round((gauss_forecast / 1000) * w_to_wh_factor, 4)

    def event_market_cycle(self):
        super().event_market_cycle()
        self.event_market_cycle_price()

    def event_market_cycle_price(self):
        self.offer_update.update_market_cycle_offers(self)

        # Iterate over all markets open in the future
        for market in self.area.all_markets:
            assert self.state.available_energy_kWh[market.time_slot] >= -FLOATING_POINT_TOLERANCE
            if self.state.available_energy_kWh[market.time_slot] > 0:
                offer_price = \
                    self.offer_update.initial_rate[market.time_slot] * \
                    self.state.available_energy_kWh[market.time_slot]
                offer = market.offer(
                    offer_price,
                    self.state.available_energy_kWh[market.time_slot],
                    self.owner.name,
                    original_offer_price=offer_price,
                    seller_origin=self.owner.name
                )
                self.offers.post(offer, market.id)

    def event_trade(self, *, market_id, trade):
        super().event_trade(market_id=market_id, trade=trade)
        market = self.area.get_future_market_from_id(market_id)
        if market is None:
            return

        assert_if_trade_offer_price_is_too_low(self, market_id, trade)

        if trade.seller == self.owner.name:
            self.state.available_energy_kWh[market.time_slot] -= trade.offer.energy

    def _set_alternative_pricing_scheme(self):
        if ConstSettings.IAASettings.AlternativePricing.PRICING_SCHEME != 0:
            if ConstSettings.IAASettings.AlternativePricing.PRICING_SCHEME == 1:
                for time_slot in generate_market_slot_list():
                    self.offer_update.reassign_mixin_arguments(time_slot, initial_rate=0,
                                                               final_rate=0)
            elif ConstSettings.IAASettings.AlternativePricing.PRICING_SCHEME == 2:
                for time_slot in generate_market_slot_list():
                    rate = \
                        self.area.config.market_maker_rate[time_slot] * \
                        ConstSettings.IAASettings.AlternativePricing.FEED_IN_TARIFF_PERCENTAGE / \
                        100
                    self.offer_update.reassign_mixin_arguments(time_slot, initial_rate=rate,
                                                               final_rate=rate)
            elif ConstSettings.IAASettings.AlternativePricing.PRICING_SCHEME == 3:
                for time_slot in generate_market_slot_list():
                    rate = self.area.config.market_maker_rate[time_slot]
                    self.offer_update.reassign_mixin_arguments(time_slot, initial_rate=rate,
                                                               final_rate=rate)
            else:
                raise MarketException
