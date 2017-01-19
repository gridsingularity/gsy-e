import math

from d3a.models.strategy.base import BaseStrategy
from d3a.models.strategy.const import DEFAULT_RISK, MAX_RISK


class PVStrategy(BaseStrategy):
    def __init__(self, panel_count=1, risk=DEFAULT_RISK):
        super().__init__()
        self.risk = risk
        self.offers_posted = {}  # type: Dict[str, Market]
        self.panel_count = panel_count

    def event_tick(self, *, area):
        # Here you can change between different forecast functions
        # This gives us a pendulum object with today 8 o'clock
        midnight = self.area.now.start_of("day").hour_(0)
        # This returns the difference to 8 o'clock in minutes
        difference_to_midnight_in_minutes = self.area.now.diff(midnight).in_minutes()
        # If we passed midnight this is a negative value, but we want the time
        # that passed since it was 8 in the morning (start of PV dataset)
        # Therefore we need to add 60 minutes times 16 (24-8) Hours
        # And use the difference between the time difference and the time passed between
        # midnight and 8 am
        if difference_to_midnight_in_minutes < 0:
            difference_to_midnight_in_minutes = (abs(60 * 8 + difference_to_midnight_in_minutes)
                                                 + 60 * 16
                                                 )
        # This function returns a forecast in the unit of kWh
#        self.log.info("current forecast is %s",
#                      self.gaussian_energy_forecast(difference_to_midnight_in_minutes))

        quantity_forecast = self.produced_energy_forecast_real_data(
            difference_to_midnight_in_minutes)
        average_market_price = self.area.historical_avg_price
        # Needed to calculate risk_dependency_of_selling_price
        normed_risk = ((self.risk - (0.5 * MAX_RISK)) / (0.5 * MAX_RISK))
        # risk_dependency_of_selling_price variates with the risk around the average market price
        # High risk means expensive selling price & high possibility not selling the energy
        # The value 0.1 is to damp the effect of the risk
        risk_dependency_of_selling_price = (normed_risk * 0.1 * average_market_price)
        energy_price = min(average_market_price + risk_dependency_of_selling_price, 30)
        rounded_energy_price = round(energy_price, 2)
        # This lets the pv system sleep if there are no offers in any markets (cold start)
        if rounded_energy_price == 0.0:
            # FIXME Price?
            rounded_energy_price = 22.5
        # Debugging print
        # print('rounded_energy_price is %s' % rounded_energy_price)
        # Iterate over all markets open in the future
        for (time, market) in self.area.markets.items():
            # If there is no offer for a currently open marketplace:
            if market not in self.offers_posted.values():
                # Sell energy and save that an offer was posted into a list
                if quantity_forecast[time] == 0:
                    continue
                for i in range(self.panel_count):
                    offer = market.offer(
                        quantity_forecast[time],
                        min((rounded_energy_price * quantity_forecast[time]), 29.9),
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

    def produced_energy_forecast_sinus(self):
        # Assuming that its 12hr when current_simulation_step = 0
        # Please see https://github.com/nrcharles/solpy
        # Might be the best way to get a realistic forecast
        # For now: use sinus function with Phase shift --> Simulation starts at 8:00 am
        past_markets = len(self.area.past_markets)
        energy_production_forecast = {}
        # Assuming 3 am is the darkest time a day --> sin(3 am) = 0
        phase_shift = 5 / 24
        # sin_amplitude / 2 should equal the maximum possible output (in wH) the pv can deliver
        sin_amplitude = 0.1
        # Sinus_offset to prevent that we get negative energy estimations
        sinus_offset = sin_amplitude
        # enumerate counts the markets through - from 0 to n
        minutes_of_one_day = 1440
        #
        for i, (time, market) in enumerate(self.area.markets.items()):
            energy_production_forecast[time] = round(
                (sin_amplitude * math.sin(
                    ((past_markets + i) / minutes_of_one_day
                     ) * 2 * math.pi + phase_shift)
                 ) + sinus_offset, 4
            )
        return energy_production_forecast

    def produced_energy_forecast_real_data(self, time_in_minutes=0):
        # This forecast ist based on the real PV system data provided by enphase
        # They can be found in the tools folder
        # A fit of a gaussian function to those data results in a formula Energy(time)
        energy_production_forecast = {}
        for time, market in self.area.markets.items():
            energy_production_forecast[time] = self.gaussian_energy_forecast(time_in_minutes)
        return energy_production_forecast

    def gaussian_energy_forecast(self, time_in_minutes=0):
        # The sun rises at approx 6:30 and sets at 18hr
        if (8 * 60 / 5) < time_in_minutes < (17.5 * 60 / 5):
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

    def event_market_cycle(self):
        pass

    def event_trade(self, *, market, trade):
        pass
