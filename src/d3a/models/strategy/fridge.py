from d3a.exceptions import MarketException
from d3a.models.area import MARKET_SLOT_LENGTH
from d3a.models.strategy.base import BaseStrategy
from d3a.models.strategy.const import DEFAULT_RISK, FRIDGE_TEMPERATURE, MAX_FRIDGE_TEMP, \
    MIN_FRIDGE_TEMP, FRIDGE_MIN_NEEDED_ENERGY, MAX_RISK


class FridgeStrategy(BaseStrategy):
    def __init__(self, risk=DEFAULT_RISK):
        super().__init__()
        self.risk = risk()
        self.offers_posted = {}  # type: Dict[str, Market]
        self.fridge_temp = FRIDGE_TEMPERATURE
        self.threshold_price = 0.0

    def event_tick(self, *, area):
        # Assuming a linear correlation between accepted price and risk
        # Used as acceptable points
        # (Risk = 1, Price = 20);(Risk = 50, Price = 15);(Risk = 100, Price = 10)
        # If risk is at average the accepted price should be less or equal the average pr
        max_risk = MAX_RISK
        average_risk = max_risk / 2
        # TODO: need to get those values from the area
        max_historical_price = 20
        min_historical_price = 10
        average_market_price = self.area.historical_avg_price
        fridge_temp_domain = MAX_FRIDGE_TEMP - MIN_FRIDGE_TEMP
        # Should have a value between 1 and -1 while T=8 should result in 1
        normalized_fridge_temp = (
            (self.fridge_temp - (0.5 * (MAX_FRIDGE_TEMP + MIN_FRIDGE_TEMP))
             ) / (0.5 * fridge_temp_domain)
        )
        # deviation_from_average is the value that determines the deviation
        # (in percentage of the average market price)
        # - using the maximum Risk strategy - of the average market price
        deviation_from_average = 0.1 * average_market_price
        # accepted_price_at_highest_risk is the threshold price while going with
        # the most risky strategy
        # This depends on the max and min historical price! (through deviation_from_average)
        accepted_price_at_highest_risk = (average_market_price - deviation_from_average)
        # This slope is used to calculate threshold prices for
        # risks other than the maximum risk strategy
        risk_price_slope = (
            (
                average_market_price - accepted_price_at_highest_risk
            ) / (max_risk - average_risk)
        )
        # risk_dependency_of_threshold_price calculates a threshold price
        # while paying respect to the risk variable therefore we use
        # the point in the risk-price domain with the lowest possible price
        # which is of course the point of highest possible risk
        # Then we add the slope times the risk (lower risk needs to result in a higher price)
        risk_dependency_of_threshold_price = (accepted_price_at_highest_risk +
                                              (MAX_RISK - self.risk) * risk_price_slope
                                              )
        # temperature_dependency_of_threshold_price calculates the Y intercept that results
        # out of a different temperature of the fridge
        # If the fridge_temp is 8 degrees the fridge needs to cool no matter how high the price is
        # If hte fridge_temp is 4 degrees the fridge can't cool no matter how low the price is
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
        next_market = list(self.area.markets.values())[0]
        # Here starts the logic if energy should be bought
        for offer in next_market.sorted_offers:
            if (
                offer.price <= threshold_price
                and self.fridge_temp > MIN_FRIDGE_TEMP
                and offer.energy >= FRIDGE_MIN_NEEDED_ENERGY
            ):
                try:
                    next_market.accept_offer(offer, self.area.name)
                    self.log.debug("Buying %s", offer)
                    # TODO: Set realistic temperature change
                    # Factor 2 compensates that we not only cool but avoid defrost as well
                    self.fridge_temp -= 2 * (offer.energy / FRIDGE_MIN_NEEDED_ENERGY) * 0.01
                    break
                except MarketException:
                    # Offer already gone etc., try next one.
                    continue

    def event_market_cycle(self):
        # TODO: Set realistic temperature change
        self.fridge_temp += MARKET_SLOT_LENGTH * 0.02
