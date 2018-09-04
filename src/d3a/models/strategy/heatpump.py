from d3a.exceptions import MarketException
from d3a.models.strategy.base import BaseStrategy
from d3a.models.strategy.const import ConstSettings


# The heat pump uses a surface collector with a season depended outside temperature
# Currently the heat pump pays no respect to the filling capacity of the storage!
class HeatPumpStrategy(BaseStrategy):
    parameters = ('risk',)

    def __init__(self, risk=ConstSettings.DEFAULT_RISK):
        if not 0 <= risk <= 100:
            raise ValueError("Risk is a percentage value, should be between 0 and 100.")
        super().__init__()
        self.risk = risk
        self.threshold_price = 0.0
        self.earth_temp = ConstSettings.EARTH_TEMP
        # The current temperature of the water storage coupled to the heat pump
        self.storage_temp = ConstSettings.INITIAL_PUMP_STORAGE_TEMP

    def event_tick(self, *, area):
        # Temperature losses are negligible (0,04 W * m^2)/mK

        # Only trade in later half of slot
        tick_in_slot = area.current_tick % area.config.ticks_per_slot
        if tick_in_slot == 1:
            return

        # THIS LOGIC IS MOSTLY SHARED WITH THE FRIDGE!!!
        # Assuming a linear correlation between accepted price and risk
        max_risk = ConstSettings.MAX_RISK
        median_risk = max_risk / 2
        # The threshold buying price depends on historical market data
        min_historical_price, max_historical_price = self.area.historical_min_max_price
        average_market_price = self.area.historical_avg_rate
        storage_temp_domain = ConstSettings.MAX_STORAGE_TEMP - ConstSettings.MIN_STORAGE_TEMP
        # normalized_storage_temp has a value between 1 and -1
        # If self.storage_temp = 30 the normalized_storage_temp is 1
        normalized_storage_temp = (
            ((0.5 * (ConstSettings.MAX_STORAGE_TEMP + ConstSettings.MIN_STORAGE_TEMP) -
              self.storage_temp)) / (0.5 * storage_temp_domain)
        )
        # deviation_from_average is the value that determines the deviation (in percentage of
        # the average market price) - this will later be multiplied with the risk
        max_deviation_from_average = 0.04 * average_market_price
        # accepted_price_at_highest_risk is the threshold price while going with the most risky
        # strategy This depends on the max and min historical price! (through the variable
        # deviation_from_average)
        accepted_price_at_highest_risk = (average_market_price - max_deviation_from_average)
        # This slope is used to calculate threshold prices for
        # risks other than the maximum risk strategy
        risk_price_slope = (
            (
                average_market_price - accepted_price_at_highest_risk
            ) / (max_risk - median_risk)
        )
        # risk_dependency_of_threshold_price calculates a threshold price
        # while paying respect to the risk variable therefore we use
        # the point in the risk-price domain with the lowest possible price
        # which is of course the point of highest possible risk
        # Then we add the slope times the risk (lower risk needs to result in a higher price)
        risk_dependency_of_threshold_price = (accepted_price_at_highest_risk +
                                              ((ConstSettings.MAX_RISK - self.risk) / 100) *
                                              risk_price_slope
                                              )

        # temperature_dependency_of_threshold_price calculates the Y intercept that results
        # out of a different temperature of the storage
        # If the storage_temp is 30 degrees the storage_temp needs to heat -
        # no matter how high the price is
        # If the storage_temp is 55 degrees the storage_temp can't heat -
        # no matter how low the price is
        # If the normalized storage_temp temp is above the average value -
        # we are tempted to heat more
        # If the normalized storage_temp temp is below the average value -
        # we are tempted to heat less
        if normalized_storage_temp >= 0:
            temperature_dependency_of_threshold_price = normalized_storage_temp * (
                max_historical_price - risk_dependency_of_threshold_price
            )
        else:
            temperature_dependency_of_threshold_price = normalized_storage_temp * (
                risk_dependency_of_threshold_price - min_historical_price
            )
        threshold_price = (
                                risk_dependency_of_threshold_price +
                                temperature_dependency_of_threshold_price
                           )
        next_market = list(self.area.markets.values())[0]
        #        self.log.info("Threshold_price is %s", threshold_price)

        # Here starts the logic if energy should be bought
        for offer in next_market.sorted_offers:
            # offer.energy * 1000 is needed to get the energy in Wh
            # For PUMP_MIN_TEMP_INCREASE see constant.py file
            heating_temperature = ((
                                    (offer.energy * 1000) / ConstSettings.PUMP_MIN_NEEDED_ENERGY)
                                   * ConstSettings.PUMP_MIN_TEMP_INCREASE
                                   )
            if (
                        (
                                (
                                    (offer.price / offer.energy) <= threshold_price
                                    and self.storage_temp + heating_temperature <
                                    ConstSettings.MAX_STORAGE_TEMP
                                )
                                or self.storage_temp <= ConstSettings.MIN_STORAGE_TEMP
                        )
                    and (offer.energy * 1000) >= ConstSettings.PUMP_MIN_NEEDED_ENERGY
            ):
                try:
                    self.accept_offer(next_market, offer)
                    self.log.debug("Buying %s", offer)
                    # TODO: Set realistic temperature change
                    self.storage_temp += heating_temperature
                    break
                except MarketException:
                    # Offer already gone etc., try next one.
                    self.log.exception("Couldn't buy")
                    continue
        else:
            if self.storage_temp < ConstSettings.MIN_STORAGE_TEMP:
                self.log.critical("Need energy (temp: %.2f) but can't buy", self.storage_temp)
                try:
                    self.log.info("cheapest price is is %s",
                                  list(next_market.sorted_offers)[-1].price)
                except IndexError:
                    self.log.critical("Crap no offers available")
