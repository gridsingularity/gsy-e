import csv
from typing import Dict  # noqa

from pendulum import Time, Interval  # noqa

from d3a.exceptions import MarketException
from d3a.models.events import Trigger
from d3a.models.strategy.base import BaseStrategy
from d3a.models.strategy.const import DEFAULT_RISK, MAX_RISK, MAX_ENERGY_PRICE, \
    MIN_PV_SELLING_PRICE


class PVPredefinedStrategy(BaseStrategy):
    available_triggers = [
        Trigger('risk', {'new_risk': int},
                help="Change the risk parameter. Valid values are between 1 and 100.")
    ]

    parameters = ('panel_count', 'risk')

    def __init__(self, path, risk=DEFAULT_RISK, min_selling_price=MIN_PV_SELLING_PRICE):
        super().__init__()
        self.data = {}
        self.readCSV(path)
        self.risk = risk
        self.energy_production_forecast_kWh = {}  # type: Dict[Time, float]
        self.midnight = None
        self.min_selling_price = min_selling_price

    def readCSV(self, path):
        with open(path) as csvfile:
            next(csvfile)
            readCSV = csv.reader(csvfile, delimiter=';')
            # self.rows = [r for r in readCSV]
            # print(self.rows)
            for row in readCSV:
                k, v = row
                self.data[k] = float(v)

    def event_activate(self):
        # This gives us a pendulum object with today 0 o'clock
        self.midnight = self.area.now.start_of("day").hour_(0)
        # Calculating the produced energy
        self.produced_energy_forecast_real_data()

    def event_tick(self, *, area):
        if (self.area.historical_avg_price == 0):
            average_market_price = MAX_ENERGY_PRICE
        else:
            average_market_price = self.area.historical_avg_price
        # Needed to calculate risk_dependency_of_selling_price
        # if risk 0-100 then energy_price less than average_market_price
        # if risk >100 then energy_price more than average_market_price
        risk_dependency_of_selling_price = ((self.risk/MAX_RISK) - 1) * average_market_price
        energy_price = max(average_market_price + risk_dependency_of_selling_price,
                           self.min_selling_price)
        rounded_energy_price = round(energy_price, 2)
        # This lets the pv system sleep if there are no offers in any markets (cold start)
        if rounded_energy_price == 0.0:
            # Initial selling offer
            rounded_energy_price = MAX_ENERGY_PRICE
        # Debugging print
        # print('rounded_energy_price is %s' % rounded_energy_price)
        # Iterate over all markets open in the future
        for (time, market) in self.area.markets.items():
            # If there is no offer for a currently open marketplace:
            if market not in self.offers.posted.values():
                # Sell energy and save that an offer was posted into a list
                try:
                    if self.energy_production_forecast_kWh[time] == 0:
                        continue
#                    for i in range(self.panel_count):
                    offer = market.offer(
                        (rounded_energy_price) *
                        self.energy_production_forecast_kWh[time],
                        self.energy_production_forecast_kWh[time],
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
            print("Slot Time: {}".format(slot_time.format('%H:%M')))

            self.energy_production_forecast_kWh[slot_time] = self.data[slot_time.format('%H:%M')]

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
