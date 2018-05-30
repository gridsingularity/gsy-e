from d3a.exceptions import MarketException
from d3a.models.state import FridgeState
from d3a.models.strategy.base import BaseStrategy
from d3a.models.strategy.const import DEFAULT_RISK, FRIDGE_MIN_NEEDED_ENERGY, MAX_RISK


# TODO Find realistic values for consumption as well as temperature changes

class FridgeStrategy(BaseStrategy):
    # TODO: Sanitize risk parameter
    parameters = ('risk',)

    def __init__(self, risk=DEFAULT_RISK):
        super().__init__()
        self.risk = risk
        self.state = FridgeState()
        self.open_spot_markets = []
        self.threshold_price = 0

    @property
    def temp_history(self):
        return self.state.temp_history

    @property
    def fridge_temp(self):
        return self.state.temperature

    def event_activate(self):
        self.open_spot_markets = list(self.area.markets.values())

    def event_tick(self, *, area):
        self.state.tick(self.area)

        # Only trade after the 4th tick
        tick_in_slot = area.current_tick % area.config.ticks_per_slot
        if tick_in_slot < 5:
            return

        # Assuming a linear correlation between accepted price and risk
        median_risk = MAX_RISK / 2
        # The threshold buying price depends on historical market data
        min_historical_price, max_historical_price = self.area.historical_min_max_price
        average_market_price = self.area.historical_avg_price

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

        if self.state.normalized_temperature >= 0:
            temperature_dependency_of_threshold_price = self.state.normalized_temperature * (
                max_historical_price - risk_dependency_of_threshold_price
            )
        else:
            temperature_dependency_of_threshold_price = self.state.normalized_temperature * (
                risk_dependency_of_threshold_price - min_historical_price
            )
        threshold_price = (risk_dependency_of_threshold_price +
                           temperature_dependency_of_threshold_price
                           )

        self.threshold_price = threshold_price

        # Here starts the logic if energy should be bought
        for market in self.open_spot_markets:
            for offer in market.sorted_offers:
                # offer.energy * 1000 is needed to get the energy in Wh
                # 0.05 is the temperature decrease per cooling period and minimal needed energy
                # *2 is needed because we need to cool and equalize the increase
                #  of the temperature (see event_market_cycle) as well
                if self.state.temperature <= self.state.min_temperature + 0.05:
                    return
                if offer.energy * 1000 < FRIDGE_MIN_NEEDED_ENERGY:
                    continue
                cooling_temperature = (((offer.energy * 1000) / FRIDGE_MIN_NEEDED_ENERGY)
                                       * 0.05 * 2)
                if (
                            ((offer.price / offer.energy) <= threshold_price
                             or self.state.temperature >= self.state.max_temperature
                             )
                ):
                    if self.state.temperature - cooling_temperature < self.state.min_temperature:
                        cooling_temperature = self.state.temperature - self.state.min_temperature
                        partial = cooling_temperature * FRIDGE_MIN_NEEDED_ENERGY / (.05 * 2 * 1000)
                    else:
                        partial = None
                    try:
                        self.accept_offer(market, offer, energy=partial)
                        self.log.debug("Buying %s", offer)
                        self.state.temperature -= cooling_temperature
                        break
                    except MarketException:
                        # Offer already gone etc., try next one.
                        self.log.exception("Couldn't buy")
                        continue
        else:
            try:
                cheapest_offer = sorted(
                    [offer for market in self.open_spot_markets
                     for offer in market.sorted_offers],
                    key=lambda o: o.price / o.energy)[0]
                if self.state.temperature >= self.state.max_temperature and \
                        (cheapest_offer.price / cheapest_offer.energy) > threshold_price:
                    self.log.critical("Need energy (temp: %.2f) but can't buy",
                                      self.state.temperature)
                    self.log.info("cheapest price is is %s", cheapest_offer.price)
            except IndexError:
                self.log.critical("Crap no offers available")

    def event_market_cycle(self):
        self.log.info("Temperature: %.2f", self.state.temperature)
        # This happens on the first market cycle, if there is no current_market
        # (AKA the most recent of the past markets) don't update the fridge state
        if self.area.current_market is not None:
            self.state.market_cycle(self.area)
        self.open_spot_markets = list(self.area.markets.values())
