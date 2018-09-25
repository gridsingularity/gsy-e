from typing import Dict  # noqa
from pendulum import Time # noqa
import math
from pendulum import duration

from d3a.models.events import Trigger
from d3a.models.strategy.base import BaseStrategy
from d3a.models.strategy.const import ConstSettings
from d3a.models.strategy.update_frequency import OfferUpdateFrequencyMixin


class PVStrategy(BaseStrategy, OfferUpdateFrequencyMixin):
    available_triggers = [
        Trigger('risk', {'new_risk': int},
                help="Change the risk parameter. Valid values are between 1 and 100.")
    ]

    parameters = ('panel_count', 'risk')

    def __init__(self, panel_count: int=1, risk: float=ConstSettings.DEFAULT_RISK,
                 min_selling_rate: float=ConstSettings.MIN_PV_SELLING_RATE,
                 initial_rate_option: float=ConstSettings.INITIAL_PV_RATE_OPTION,
                 energy_rate_decrease_option: int=ConstSettings.PV_RATE_DECREASE_OPTION,
                 energy_rate_decrease_per_update: float=ConstSettings.ENERGY_RATE_DECREASE_PER_UPDATE):  # NOQA
        self._validate_constructor_arguments(panel_count, risk)
        BaseStrategy.__init__(self)
        OfferUpdateFrequencyMixin.__init__(self, initial_rate_option,
                                           energy_rate_decrease_option,
                                           energy_rate_decrease_per_update)
        self.risk = risk
        self.panel_count = panel_count
        self.midnight = None
        self.min_selling_rate = min_selling_rate
        self.energy_production_forecast_kWh = {}  # type: Dict[Time, float]

    @staticmethod
    def _validate_constructor_arguments(panel_count, risk):
        if not (0 <= risk <= 100 and panel_count >= 1):
            raise ValueError("Risk is a percentage value, should be "
                             "between 0 and 100, panel_count should be positive.")

    def event_activate(self):
        # This gives us a pendulum object with today 0 o'clock
        self.midnight = self.area.now.start_of("day")
        # Calculating the produced energy
        self.update_on_activate()
        for slot_time in [
                    self.area.now + (self.area.config.slot_length * i)
                    for i in range(
                        (
                                    self.area.config.duration
                                    + (
                                            self.area.config.market_count *
                                            self.area.config.slot_length)
                        ) // self.area.config.slot_length)
                    ]:
            self.energy_production_forecast_kWh[slot_time] = 0
        self.produced_energy_forecast_kWh()

    def _incorporate_rate_restrictions(self, initial_sell_rate, current_time):
        # Needed to calculate risk_dependency_of_selling_rate
        # if risk 0-100 then energy_price less than initial_sell_rate
        # if risk >100 then energy_price more than initial_sell_rate
        energy_rate = max(initial_sell_rate, self.min_selling_rate)
        rounded_energy_rate = round(energy_rate, 2)
        # This lets the pv system sleep if there are no offers in any markets (cold start)
        if rounded_energy_rate == 0.0:
            # Initial selling offer
            rounded_energy_rate =\
                self.area.config.market_maker_rate[current_time]
        assert rounded_energy_rate >= 0.0

        return rounded_energy_rate

    def event_tick(self, *, area):
        self.decrease_energy_price_over_ticks()

    def produced_energy_forecast_kWh(self):
        # This forecast ist based on the real PV system data provided by enphase
        # They can be found in the tools folder
        # A fit of a gaussian function to those data results in a formula Energy(time)
        for slot_time in self.energy_production_forecast_kWh.keys():
            difference_to_midnight_in_minutes = slot_time.diff(self.midnight).in_minutes()
            self.energy_production_forecast_kWh[slot_time] =\
                self.gaussian_energy_forecast_kWh(difference_to_midnight_in_minutes)
            assert self.energy_production_forecast_kWh[slot_time] >= 0.0

    def gaussian_energy_forecast_kWh(self, time_in_minutes=0):
        # The sun rises at approx 6:30 and sets at 18hr
        # time_in_minutes is the difference in time to midnight

        # Clamp to day range
        time_in_minutes %= 60 * 24
        peak_pv_output = ConstSettings.MAX_PV_OUTPUT

        if (8 * 60) > time_in_minutes or time_in_minutes > (16.5 * 60):
            gauss_forecast = 0

        else:
            gauss_forecast = peak_pv_output * math.exp(
                # time/5 is needed because we only have one data set per 5 minutes

                (- (((round(time_in_minutes / 5, 0)) - 147.2)
                    / 38.60) ** 2
                 )
            )
        # /1000 is needed to convert Wh into kW
        w_to_wh_factor = (self.area.config.slot_length / duration(hours=1))
        return round((gauss_forecast / 1000) * w_to_wh_factor, 4)

    def event_market_cycle(self):
        self.update_market_cycle_offers(self.min_selling_rate)
        # Iterate over all markets open in the future
        time = list(self.area.markets.keys())[0]
        market = list(self.area.markets.values())[0]
        initial_sell_rate = self.calculate_initial_sell_rate(market.time_slot_str)
        rounded_energy_rate = self._incorporate_rate_restrictions(initial_sell_rate,
                                                                  market.time_slot_str)
        # Sell energy and save that an offer was posted into a list
        if self.energy_production_forecast_kWh[time] != 0:
            offer = market.offer(
                rounded_energy_rate * self.panel_count *
                self.energy_production_forecast_kWh[time],
                self.energy_production_forecast_kWh[time] * self.panel_count,
                self.owner.name
            )
            self.offers.post(offer, market)

    def trigger_risk(self, new_risk: int = 0):
        new_risk = int(new_risk)
        if not (-1 < new_risk < 101):
            raise ValueError("'new_risk' value has to be in range 0 - 100")
        self.risk = new_risk
        self.log.warning("Risk changed to %s", new_risk)
