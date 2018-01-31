import math
from typing import Dict  # noqa

from pendulum import Time  # noqa

from d3a.exceptions import MarketException
from d3a.models.events import Trigger
from d3a.models.strategy.base import BaseStrategy
from d3a.models.strategy.const import DEFAULT_RISK, MAX_RISK


class PVStrategy(BaseStrategy):
    available_triggers = [
        Trigger('risk', {'new_risk': int},
                help="Change the risk parameter. Valid values are between 1 and 100.")
    ]

    parameters = ('panel_count', 'risk')

    def __init__(self, panel_count=1, risk=DEFAULT_RISK):
        super().__init__()
        self.risk = risk
        self.energy_production_forecast = {}  # type: Dict[Time, float]
        self.panel_count = panel_count
        self.midnight = None

    def event_activate(self):
        # This gives us a pendulum object with today 0 o'clock
        self.midnight = self.area.now.start_of("day").hour_(0)
        # Calculating the produced energy
        self.produced_energy_forecast_real_data()

    def event_tick(self, *, area):
        average_market_price = self.area.historical_avg_price
        # Needed to calculate risk_dependency_of_selling_price
        normed_risk = ((self.risk - (0.5 * MAX_RISK)) / (0.5 * MAX_RISK))
        # risk_dependency_of_selling_price variates with the risk around the average market price
        # High risk means expensive selling price & high possibility not selling the energy
        # The value 0.1 is to damp the effect of the risk
        risk_dependency_of_selling_price = (normed_risk * 0.02 * average_market_price)
        # If the risk is higher than 50 the energy_price is above the average_market_price
        energy_price = min(average_market_price + risk_dependency_of_selling_price, 29.9)
        rounded_energy_price = round(energy_price, 2)
        # This lets the pv system sleep if there are no offers in any markets (cold start)
        if rounded_energy_price == 0.0:
            # Initial selling offer
            rounded_energy_price = 29.9
        # Debugging print
        # print('rounded_energy_price is %s' % rounded_energy_price)
        # Iterate over all markets open in the future
        for (time, market) in self.area.markets.items():
            # If there is no offer for a currently open marketplace:
            if market not in self.offers.posted.values():
                # Sell energy and save that an offer was posted into a list
                try:
                    if self.energy_production_forecast[time] == 0:
                        continue
                    for i in range(self.panel_count):
                        offer = market.offer(
                            (min(rounded_energy_price, 29.9)) *
                            self.energy_production_forecast[time],
                            self.energy_production_forecast[time],
                            self.owner.name
                        )
                        self.offers.post(offer, market)

                except KeyError:
                    self.log.warn("PV has no forecast data for this time")
                    continue

            else:
                pass

        # Decrease the selling price over the ticks in a slot
        if (
                self.area.current_tick % self.area.config.ticks_per_slot >
                self.area.config.ticks_per_slot * 0.1
                and
                # FIXME: MAke sure that the offer reached every system participant.
                # FIXME: Therefore it can only be update (depending on number of niveau and
                # FIXME: InterAreaAgent min_offer_age
                self.area.current_tick % 7 == 0
        ):
            next_market = list(self.area.markets.values())[0]
            self.decrease_offer_price(next_market)

    def produced_energy_forecast_real_data(self):
        # This forecast ist based on the real PV system data provided by enphase
        # They can be found in the tools folder
        # A fit of a gaussian function to those data results in a formula Energy(time)
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
            difference_to_midnight_in_minutes = slot_time.diff(self.midnight).in_minutes()
            self.energy_production_forecast[slot_time] = self.gaussian_energy_forecast(
                difference_to_midnight_in_minutes
            )

    def gaussian_energy_forecast(self, time_in_minutes=0):
        # The sun rises at approx 6:30 and sets at 18hr
        # time_in_minutes is the difference in time to midnight

        # Clamp to day range
        time_in_minutes %= 60 * 24

        if (8 * 60) > time_in_minutes or time_in_minutes > (16.5 * 60):
            gauss_forecast = 0

        else:
            gauss_forecast = 166.54 * math.exp(
                # time/5 is needed because we only have one data set per 5 minutes
                (- (((round(time_in_minutes / 5, 0)) - 147.2)
                    / 38.60) ** 2
                 )
            )
        # /1000 is needed to convert Wh into kWh
        return round((gauss_forecast / 1000), 4)

    def decrease_offer_price(self, market):
        if market not in self.offers.open.values():
            return
        for offer, iterated_market in self.offers.open.items():
            if iterated_market != market:
                continue
            try:
                iterated_market.delete_offer(offer.id)
                new_offer = iterated_market.offer(
                    offer.price * 0.99,
                    offer.energy,
                    self.owner.name
                )
                self.offers.replace(offer, new_offer, iterated_market)

            except MarketException:
                continue

    def event_market_cycle(self):
        pass

    def trigger_risk(self, new_risk: int = 0):
        new_risk = int(new_risk)
        if not (-1 < new_risk < 101):
            raise ValueError("'new_risk' value has to be in range 0 - 100")
        self.risk = new_risk
        self.log.warn("Risk changed to %s", new_risk)
