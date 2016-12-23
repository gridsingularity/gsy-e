import math

from d3a.models.strategy.base import BaseStrategy
from d3a.models.strategy.const import DEFAULT_RISK, MAX_RISK, MIN_PV_SELLING_PRICE


class PVStrategy(BaseStrategy):
    def __init__(self, risk=DEFAULT_RISK):
        super().__init__()
        self.risk = risk
        self.offers_posted = {}  # type: Dict[str, Market]

    def event_tick(self, *, area):
        quantity_forecast = self.produced_energy_forecast()
        average_market_price = self.area.historical_avg_price
        # Needed to calculate risk_dependency_of_selling_price
        normed_risk = ((self.risk - 0.5 * MAX_RISK) / 0.5 * MAX_RISK)
        # risk_dependency_of_selling_price variates with the risk around the average market price
        # High risk means expensive selling price & high possibility not selling the energy
        risk_dependency_of_selling_price = (normed_risk * 0.4 * average_market_price)
        energy_price = max(average_market_price + risk_dependency_of_selling_price,
                           MIN_PV_SELLING_PRICE)
        rounded_energy_price = round(energy_price, 2)
        # Debugging print
        # print('rounded_energy_price is %s' % rounded_energy_price)
        # Iterate over all markets open in the future
        for (time, market) in self.area.markets.items():
            # If there is no offer for a currently open marketplace:
            if market not in self.offers_posted.values():
                # Sell energy and save that an offer was posted into a list
                offer = market.offer(
                    quantity_forecast[time],
                    rounded_energy_price,
                    self.owner.name
                )
                self.offers_posted[offer.id] = market
            else:
                # XXX TODO: This should check if current market offers
                # are still in line with strategy
                # if self.offers_posted_in_market[
                #                                   self.passed_markets + open_future_markets
                #                                    ] != energy_price:
                # self.delete_offer()
                # self.sell_energy(... see above)
                pass

    def produced_energy_forecast(self):
        # Assuming that its 12hr when current_simulation_step = 0
        # Please see https://github.com/nrcharles/solpy
        # Might be the best way to get a realistic forecast
        # For now: use sinus function with Phase shift --> Simulation starts at 8:00 am
        past_markets = len(self.area.past_markets)
        energy_production_forecast = {}
        # Assuming 3 am is the darkest time a day --> sin(3 am) = 0
        phase_shift = 5 / 24
        # sin_amplitude / 2 should equal the maximum possible output (in kw) the pv can deliver
        sin_amplitude = 50
        # Sinus_offset to prevent that we get negative energy estimations
        sinus_offset = sin_amplitude
        # enumerate counts the markets through - from 0 to n
        minutes_of_one_day = 1440
        #
        for i, (time, market) in enumerate(self.area.markets.items()):
            energy_production_forecast[time] = round(
                (sin_amplitude * math.sin(
                    ((past_markets + i) / minutes_of_one_day
                     ) * 2 * math.pi + phase_shift)) + sinus_offset, 2)
        return energy_production_forecast

    def event_market_cycle(self):
        pass

    def event_trade(self, *, market, trade):
        pass
