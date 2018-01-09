from typing import Dict, Any  # noqa
from collections import defaultdict

from d3a.exceptions import MarketException
from d3a.models.strategy.base import BaseStrategy
from d3a.models.strategy.const import DEFAULT_RISK, FRIDGE_TEMPERATURE, MAX_FRIDGE_TEMP, \
    MIN_FRIDGE_TEMP, FRIDGE_MIN_NEEDED_ENERGY, MAX_RISK


# TODO Find realistic values for consumption as well as temperature changes

class FridgeStrategy(BaseStrategy):
    parameters = ('risk',)

    def __init__(self, risk=DEFAULT_RISK):
        super().__init__()
        self.risk = risk
        self.fridge_temp = FRIDGE_TEMPERATURE
        self.open_spot_markets = []
        self.max_fridge_temp = 0
        self.min_fridge_temp = 0
        self.temp_history = defaultdict(lambda: '-')
        self.threshold_price = 0

    def event_activate(self):
        self.open_spot_markets = list(self.area.markets.values())
        self.max_fridge_temp = MAX_FRIDGE_TEMP
        self.min_fridge_temp = MIN_FRIDGE_TEMP

    def event_tick(self, *, area):
        # The not cooled fridge warms up (0.02 / 60)C up every second
        self.fridge_temp += self.area.config.tick_length.in_seconds() * round((0.02 / 60), 6)

        # Only trade after the 4th tick
        tick_in_slot = area.current_tick % area.config.ticks_per_slot
        if tick_in_slot < 5:
            return

        self.calc_threshold_price()

        # Here starts the logic if energy should be bought
        for market in self.open_spot_markets:
            for offer in market.sorted_offers:
                # offer.energy * 1000 is needed to get the energy in Wh
                # 0.05 is the temperature decrease per cooling period and minimal needed energy
                # *2 is needed because we need to cool and equalize the increase
                #  of the temperature (see event_market_cycle) as well
                cooling_temperature = (((offer.energy * 1000) / FRIDGE_MIN_NEEDED_ENERGY)
                                       * 0.05 * 2)
                if (
                            (((offer.price / offer.energy) <= self.threshold_price
                              and self.fridge_temp - cooling_temperature > self.min_fridge_temp
                              )
                             or self.fridge_temp >= self.max_fridge_temp
                             )
                        and (offer.energy * 1000) >= FRIDGE_MIN_NEEDED_ENERGY
                ):
                    try:
                        self.accept_offer(market, offer)
                        self.log.debug("Buying %s", offer)
                        self.fridge_temp -= cooling_temperature
                        self.calc_threshold_price()
                        break
                    except MarketException:
                        # Offer already gone etc., try next one.
                        self.log.exception("Couldn't buy")
                        continue
                else:
                    try:
                        cheapest_offer = sorted(
                            [offer for market in self.open_spot_markets for
                             offer in market.sorted_offers],
                            key=lambda o: o.price / o.energy)[0]
                        if self.fridge_temp >= MAX_FRIDGE_TEMP and \
                                ((cheapest_offer.price / cheapest_offer.energy) >
                                    self.threshold_price):
                            self.log.critical("Need energy (temp: %.2f) but can't buy",
                                              self.fridge_temp)
                            self.log.info("cheapest price is is %s", cheapest_offer.price)
                    except IndexError:
                        self.log.critical("Crap no offers available")

    def event_market_cycle(self):
        self.log.info("Temperature: %.2f", self.fridge_temp)
        self.temp_history[self.area.current_market.time_slot] = self.fridge_temp
        self.open_spot_markets = list(self.area.markets.values())

    def event_data_received(self, data: Dict[str, Any]):
        # self.fridge_temp += data.get("temperature_change", 0)
        if "temperature" in data:
            self.fridge_temp += data.get("temperature")

    def calc_threshold_price(self):

        # Assuming a linear correlation between accepted price and risk
        median_risk = MAX_RISK / 2
        # The threshold buying price depends on historical market data
        min_historical_price, max_historical_price = self.area.historical_min_max_price
        average_market_price = self.area.historical_avg_price
        fridge_temp_domain = MAX_FRIDGE_TEMP - MIN_FRIDGE_TEMP

        # normalized _fridge_temp has a value between 1 and -1
        # If self.fridge_temp = 8 the normalized_fridge_temp is 1
        normalized_fridge_temp = (
            (self.fridge_temp - (0.5 * (MAX_FRIDGE_TEMP + MIN_FRIDGE_TEMP))
             ) / (0.5 * fridge_temp_domain)
        )

        # deviation_from_average is the value that determines the deviation (in percentage of
        # the average market price)
        max_deviation_from_average = 0.1 * average_market_price

        # accepted_price_at_highest_risk is the threshold price while going with the most risky
        # strategy This depends on the max and min historical price! (through the variable
        # deviation_from_average)
        accepted_price_at_highest_risk = (average_market_price - max_deviation_from_average)

        # This slope is used to calculate threshold prices for
        # risks other than the maximum risk strategy
        risk_price_slope = (
            (
                average_market_price - accepted_price_at_highest_risk
            ) / (MAX_RISK - median_risk)
        )

        # risk_dependency_of_threshold_price calculates a threshold price
        # with respect to the risk variable. Therefore, we use
        # the point in the risk-price domain with the lowest possible price.
        # This is of course the point of highest possible risk.
        # Then we add the slope times the risk (lower risk needs to result in a higher price)
        risk_dependency_of_threshold_price = (accepted_price_at_highest_risk +
                                              ((MAX_RISK - self.risk) / 100) * risk_price_slope
                                              )

        # temperature_dependency_of_threshold_price calculates the Y intercept that results
        # out of a different temperature of the fridge
        # If the fridge_temp is 8 degrees the fridge needs to cool no matter how high the price is
        # If the fridge_temp is 4 degrees the fridge can't cool no matter how low the price is
        # If the normalized fridge temp is above the average value we are tempted to cool more
        # If the normalized fridge temp is below the average value we are tempted to cool less
        if normalized_fridge_temp >= 0:
            temperature_dependency_of_threshold_price = normalized_fridge_temp * (
                max_historical_price - risk_dependency_of_threshold_price
            )
        else:
            temperature_dependency_of_threshold_price = normalized_fridge_temp * (
                risk_dependency_of_threshold_price - min_historical_price
            )
        threshold_price = (risk_dependency_of_threshold_price +
                           temperature_dependency_of_threshold_price
                           )

        self.threshold_price = threshold_price
