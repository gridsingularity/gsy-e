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
from pendulum import Time # noqa
import math
from pendulum import duration
from datetime import timedelta

from d3a.d3a_core.util import generate_market_slot_list
from d3a.events.event_structures import Trigger
from d3a.models.strategy import BaseStrategy
from d3a.models.const import ConstSettings
from d3a.models.strategy.update_frequency import UpdateFrequencyMixin
from d3a.models.state import PVState
from d3a.constants import FLOATING_POINT_TOLERANCE


class PVStrategy(BaseStrategy):
    available_triggers = [
        Trigger('risk', {'new_risk': int},
                help="Change the risk parameter. Valid values are between 1 and 100.")
    ]

    parameters = ('panel_count', 'initial_selling_rate', 'final_selling_rate',
                  'fit_to_limit', 'update_interval', 'energy_rate_change_per_update',
                  'max_panel_power_W')

    def __init__(self, panel_count: int=1,
                 initial_selling_rate:
                 float=ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE,
                 final_selling_rate:
                 float=ConstSettings.PVSettings.FINAL_SELLING_RATE,
                 fit_to_limit: bool=True,
                 update_interval=timedelta(minutes=ConstSettings.GeneralSettings.UPDATE_RATE),
                 energy_rate_change_per_update:
                 float=ConstSettings.GeneralSettings.ENERGY_RATE_DECREASE_PER_UPDATE,
                 max_panel_power_W: float=ConstSettings.PVSettings.MAX_PANEL_OUTPUT_W):
        """
        :param panel_count: Number of solar panels for this PV plant
        :param initial_selling_rate: Upper Threshold for PV offers
        :param final_selling_rate: Lower Threshold for PV offers
        :param fit_to_limit: Linear curve following initial_selling_rate & initial_selling_rate
        :param update_interval: Interval after which PV will update its offer
        :param energy_rate_change_per_update: Slope of PV Offer change per update
        :param max_panel_power_W:
        """
        self._validate_constructor_arguments(panel_count, max_panel_power_W,
                                             initial_selling_rate, final_selling_rate)
        BaseStrategy.__init__(self)
        self.offer_update = UpdateFrequencyMixin(initial_selling_rate, final_selling_rate,
                                                 fit_to_limit, energy_rate_change_per_update,
                                                 update_interval)
        self.panel_count = panel_count
        self.max_panel_power_W = max_panel_power_W
        self.energy_production_forecast_kWh = {}  # type: Dict[Time, float]
        self.state = PVState()

    @staticmethod
    def _validate_constructor_arguments(panel_count, max_panel_output_W,
                                        initial_selling_rate, final_selling_rate):
        if panel_count is not None and panel_count <= 0:
            raise ValueError("Number of Panels should be a non-zero and positive value.")
        if max_panel_output_W < 0:
            raise ValueError("Max panel output in Watts should always be positive.")
        if initial_selling_rate < 0:
            raise ValueError("Min selling rate should be positive.")
        if final_selling_rate < 0:
            raise ValueError("Min selling rate should be positive.")
        if initial_selling_rate < final_selling_rate:
            raise ValueError("PV should start selling high and then offer lower price")

    def area_reconfigure_event(self, **kwargs):
        assert all(k in self.parameters for k in kwargs.keys())
        self._validate_constructor_arguments(kwargs.get('panel_count', None),
                                             kwargs.get('max_panel_power_W', None),
                                             kwargs.get('initial_selling_rate', None),
                                             kwargs.get('final_selling_rate', None))
        for name, value in kwargs.items():
            setattr(self, name, value)
        self.produced_energy_forecast_kWh()

    def event_activate(self):
        # if ConstSettings.IAASettings.AlternativePricing.PRICING_SCHEME != 0:
        #     self.assign_offermixin_arguments(3, 2, 0)

        # Calculating the produced energy
        self.offer_update.update_on_activate(self)
        self.produced_energy_forecast_kWh()

    def event_tick(self, *, area):
        if self.offer_update.get_price_update_point(self):
            for market in self.area.all_markets:
                self.offer_update.update_energy_price(market, self)

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
        self.offer_update.update_market_cycle_offers(self)

        # Iterate over all markets open in the future
        for market in self.area.all_markets:
            # self.set_initial_selling_rate_alternative_pricing_scheme(market)
            # initial_sell_rate = self.calculate_initial_sell_rate(market.time_slot)
            assert self.state.available_energy_kWh[market.time_slot] >= -FLOATING_POINT_TOLERANCE
            if self.state.available_energy_kWh[market.time_slot] > 0:
                print(f"initial_rate: {self.offer_update.initial_rate}")
                offer_price = \
                    self.offer_update.initial_rate * \
                    self.state.available_energy_kWh[market.time_slot]
                offer = market.offer(
                    offer_price,
                    self.state.available_energy_kWh[market.time_slot],
                    self.owner.name,
                    original_offer_price=offer_price
                )
                self.offers.post(offer, market.id)

    def trigger_risk(self, new_risk: int = 0):
        new_risk = int(new_risk)
        if not (-1 < new_risk < 101):
            raise ValueError("'new_risk' value has to be in range 0 - 100")
        self.risk = new_risk
        self.log.info("Risk changed to %s", new_risk)

    def event_offer_deleted(self, *, market_id, offer):
        super().event_offer_deleted(market_id=market_id, offer=offer)
        market = self.area.get_future_market_from_id(market_id)
        if market is None:
            return
        # if offer was deleted but not traded, free the energy in state.available_energy_kWh again
        if offer.id not in [trades.offer.id for trades in market.trades]:
            if offer.seller == self.owner.name:
                self.state.available_energy_kWh[market.time_slot] += offer.energy

    def event_offer(self, *, market_id, offer):
        super().event_offer(market_id=market_id, offer=offer)
        market = self.area.get_future_market_from_id(market_id)
        assert market is not None

        # if offer was deleted but not traded, free the energy in state.available_energy_kWh again
        if offer.seller == self.owner.name:
            self.state.available_energy_kWh[market.time_slot] -= offer.energy
