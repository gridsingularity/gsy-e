from typing import Dict  # noqa
from pendulum import Time # noqa
import math
from pendulum import duration

from d3a.util import generate_market_slot_list
from d3a.models.events import Trigger
from d3a.models.strategy.base import BaseStrategy
from d3a.models.strategy.const import ConstSettings
from d3a.models.strategy.update_frequency import OfferUpdateFrequencyMixin
from d3a.models.state import PVState


class PVStrategy(BaseStrategy, OfferUpdateFrequencyMixin):
    available_triggers = [
        Trigger('risk', {'new_risk': int},
                help="Change the risk parameter. Valid values are between 1 and 100.")
    ]

    parameters = ('panel_count', 'risk')

    def __init__(
        self, panel_count: int=1, risk: float=ConstSettings.DEFAULT_RISK,
        min_selling_rate: float=ConstSettings.MIN_PV_SELLING_RATE,
        initial_rate_option: float=ConstSettings.INITIAL_PV_RATE_OPTION,
        energy_rate_decrease_option: int=ConstSettings.PV_RATE_DECREASE_OPTION,
        energy_rate_decrease_per_update: float=ConstSettings.ENERGY_RATE_DECREASE_PER_UPDATE,
        max_panel_power_W: float=ConstSettings.PV_MAX_PANEL_OUTPUT_W
    ):
        self._validate_constructor_arguments(panel_count, risk, max_panel_power_W)
        BaseStrategy.__init__(self)
        OfferUpdateFrequencyMixin.__init__(self, initial_rate_option,
                                           energy_rate_decrease_option,
                                           energy_rate_decrease_per_update)
        self.risk = risk
        self.panel_count = panel_count
        self.max_panel_power_W = max_panel_power_W
        self.midnight = None
        self.min_selling_rate = min_selling_rate
        self.energy_production_forecast_kWh = {}  # type: Dict[Time, float]
        self.state = PVState()

    @staticmethod
    def _validate_constructor_arguments(panel_count, risk, max_panel_output_W):
        if not (0 <= risk <= 100 and panel_count >= 1):
            raise ValueError("Risk is a percentage value, should be "
                             "between 0 and 100, panel_count should be positive.")
        if max_panel_output_W < 0:
            raise ValueError("Max panel output in Watts should always be positive.")

    def event_activate(self):
        # This gives us a pendulum object with today 0 o'clock
        self.midnight = self.area.now.start_of("day")
        # Calculating the produced energy
        self.update_on_activate()
        self.produced_energy_forecast_kWh()

    def _incorporate_rate_restrictions(self, initial_sell_rate, current_time):
        energy_rate = max(initial_sell_rate, self.min_selling_rate)
        rounded_energy_rate = round(energy_rate, 2)
        if rounded_energy_rate == 0.0:
            # Initial selling offer
            rounded_energy_rate =\
                self.area.config.market_maker_rate[current_time]
        assert rounded_energy_rate >= 0.0

        return rounded_energy_rate

    def event_tick(self, *, area):
        for market in list(self.area.markets.values()):
            self.decrease_energy_price_over_ticks(market)

    def produced_energy_forecast_kWh(self):
        # This forecast ist based on the real PV system data provided by enphase
        # They can be found in the tools folder
        # A fit of a gaussian function to those data results in a formula Energy(time)
        for slot_time in generate_market_slot_list(self.area):
            difference_to_midnight_in_minutes = slot_time.diff(self.midnight).in_minutes()
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
        self.update_market_cycle_offers(self.min_selling_rate)

        # Iterate over all markets open in the future
        for market in self.area.markets.values():
            initial_sell_rate = self.calculate_initial_sell_rate(market.time_slot_str)
            rounded_energy_rate = self._incorporate_rate_restrictions(initial_sell_rate,
                                                                      market.time_slot_str)
            assert self.state.available_energy_kWh[market.time_slot] >= -0.00001
            if self.state.available_energy_kWh[market.time_slot] > 0:
                offer = market.offer(
                    rounded_energy_rate * self.state.available_energy_kWh[market.time_slot],
                    self.state.available_energy_kWh[market.time_slot],
                    self.owner.name
                )
                self.offers.post(offer, market)

    def trigger_risk(self, new_risk: int = 0):
        new_risk = int(new_risk)
        if not (-1 < new_risk < 101):
            raise ValueError("'new_risk' value has to be in range 0 - 100")
        self.risk = new_risk
        self.log.warning("Risk changed to %s", new_risk)

    def event_offer_deleted(self, *, market, offer):
        # if offer was deleted but not traded, free the energy in state.available_energy_kWh again
        if offer.id not in [trades.offer.id for trades in market.trades]:
            if offer.seller == self.owner.name:
                self.state.available_energy_kWh[market.time_slot] += offer.energy

    def event_offer(self, *, market, offer):
        # if offer was deleted but not traded, free the energy in state.available_energy_kWh again
        if offer.id not in [trades.offer.id for trades in market.trades]:
            if offer.seller == self.owner.name:
                self.state.available_energy_kWh[market.time_slot] -= offer.energy

    def update_market_cycle_offers(self, min_selling_rate):
        self.min_selling_rate = min_selling_rate
        # increase energy rate for each market again, except for the newly created one
        for market in list(self.area.markets.values()):
            self._decrease_price_timepoint_s[market.time_slot] = self._decrease_price_every_nr_s
        for market in list(self.area.markets.values())[:-1]:
            self.reset_price_on_market_cycle(market)
