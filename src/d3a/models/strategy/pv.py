from typing import Dict  # noqa
from pendulum import Time # noqa
import math
from pendulum import Interval

from d3a.models.strategy import ureg, Q_
from d3a.exceptions import MarketException
from d3a.models.events import Trigger
from d3a.models.strategy.base import BaseStrategy
from d3a.models.strategy.const import DEFAULT_RISK, MAX_RISK, MAX_ENERGY_RATE, \
    MIN_PV_SELLING_PRICE, MAX_OFFER_TRAVERSAL_LENGTH
# PV_DECREASE_PER_SECOND_BY


class PVStrategy(BaseStrategy):
    available_triggers = [
        Trigger('risk', {'new_risk': int},
                help="Change the risk parameter. Valid values are between 1 and 100.")
    ]

    parameters = ('panel_count', 'risk')

    def __init__(self, panel_count=1, risk=DEFAULT_RISK, min_selling_price=MIN_PV_SELLING_PRICE):
        self._validate_constructor_arguments(panel_count, risk)
        super().__init__()
        self.risk = risk
        self.energy_production_forecast_kWh = {}  # type: Dict[Time, float]
        self.panel_count = panel_count
        self.midnight = None
        self.min_selling_price = Q_(min_selling_price, (ureg.EUR_cents/ureg.kWh))
        self._decrease_price_timepoint_s = 0 * ureg.seconds
        self._decrease_price_every_nr_s = 0 * ureg.seconds

    @staticmethod
    def _validate_constructor_arguments(panel_count, risk):
        if not (0 <= risk <= 100 and panel_count >= 1):
            raise ValueError("Risk is a percentage value, should be "
                             "between 0 and 100, panel_count should be positive.")

    def event_activate(self):
        # This gives us a pendulum object with today 0 o'clock
        self.midnight = self.area.now.start_of("day").hour_(0)
        # Calculating the produced energy
        self.produced_energy_forecast_real_data()
        self._decrease_price_every_nr_s = \
            (self.area.config.tick_length.seconds * MAX_OFFER_TRAVERSAL_LENGTH + 1) * ureg.seconds
        print("Time Slot for reducing offer: {}".format(self._decrease_price_every_nr_s))
        print("Slot Length: {}"
              .format(self.area.config.slot_length.seconds))
        print("Offer Update rate: {}"
              .format(int(self.area.config.slot_length.seconds
                          / self._decrease_price_every_nr_s.m)))

    def event_tick(self, *, area):
        average_market_rate = Q_(
            MAX_ENERGY_RATE if self.area.historical_avg_price == 0
            else self.area.historical_avg_price,
            ureg.EUR_cents / ureg.kWh)
        # Needed to calculate risk_dependency_of_selling_rate
        # if risk 0-100 then energy_price less than average_market_rate
        # if risk >100 then energy_price more than average_market_rate
        # risk_dependency_of_selling_rate = ((self.risk/MAX_RISK) - 1) * average_market_rate
        energy_rate = max(average_market_rate.m, self.min_selling_price.m)
        rounded_energy_rate = round(energy_rate, 2)
        # print("Historical Average price: {}".format(self.area.historical_avg_price))
        # This lets the pv system sleep if there are no offers in any markets (cold start)
        if rounded_energy_rate == 0.0:
            # Initial selling offer
            rounded_energy_rate = MAX_ENERGY_RATE
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
                    for i in range(self.panel_count):
                        offer = market.offer(
                            rounded_energy_rate *
                            self.energy_production_forecast_kWh[time],
                            self.energy_production_forecast_kWh[time],
                            self.owner.name
                        )
                        print("Posted Offer Energy: {}; Rate: {}"
                              .format(offer.energy, offer.price/offer.energy))
                        self.offers.post(offer, market)

                except KeyError:
                    self.log.warn("PV has no forecast data for this time")
                    continue

            else:
                pass
        self._decrease_energy_price_over_ticks()

    def _decrease_energy_price_over_ticks(self):
        # Decrease the selling price over the ticks in a slot
        current_tick_number = self.area.current_tick % self.area.config.ticks_per_slot
        elapsed_seconds = current_tick_number * self.area.config.tick_length.seconds * ureg.seconds
        if (
                # FIXME: Make sure that the offer reached every system participant.
                # FIXME: Therefore it can only be update (depending on number of niveau and
                # FIXME: InterAreaAgent min_offer_age
                current_tick_number > MAX_OFFER_TRAVERSAL_LENGTH
                and elapsed_seconds > self._decrease_price_timepoint_s
        ):
            self._decrease_price_timepoint_s += self._decrease_price_every_nr_s
            next_market = list(self.area.markets.values())[0]
            self.decrease_offer_price(next_market)

    def decrease_offer_price(self, market):
        if market not in self.offers.open.values():
            return
        for offer, iterated_market in self.offers.open.items():
            if iterated_market != market:
                continue
            try:
                iterated_market.delete_offer(offer.id)
                new_offer = iterated_market.offer(
                    (offer.price - self._calculate_price_decrease_rate(offer)),
                    offer.energy,
                    self.owner.name
                )
                print("Unsold Offer Energy: {}; Rate: {}"
                      .format(offer.energy, offer.price / offer.energy))
                self.offers.replace(offer, new_offer, iterated_market)
                print("Revised Offer Energy: {}; Rate: {}"
                      .format(new_offer.energy, new_offer.price / new_offer.energy))

            except MarketException:
                continue

    def _calculate_price_decrease_rate(self, offer):
        # chg = ((offer.price - MIN_PV_SELLING_PRICE * offer.energy) * (self.risk/MAX_RISK)/10)
        # print("Changed Rate: {}".format(chg/offer.energy))
        price_dec_per_slot = (offer.price - MIN_PV_SELLING_PRICE * offer.energy)\
                             * (1 - self.risk/MAX_RISK)
        price_updates_per_slot = int(self.area.config.slot_length.seconds
                                     / self._decrease_price_every_nr_s.m)
        price_dec_per_update = price_dec_per_slot / price_updates_per_slot
        return price_dec_per_update
        # return ((offer.price - MIN_PV_SELLING_PRICE * offer.energy) * (1 - self.risk/MAX_RISK)
        #         / int(self.area.config.slot_length.seconds / self._decrease_price_every_nr_s.m))
        # return 1.0 - PV_DECREASE_PER_SECOND_BY * self._decrease_price_every_nr_s.m

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
            self.energy_production_forecast_kWh[slot_time] = self.gaussian_energy_forecast_kWh(
                difference_to_midnight_in_minutes
            )

    def gaussian_energy_forecast_kWh(self, time_in_minutes=0):
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
        # /1000 is needed to convert Wh into kW
        w_to_wh_factor = (self.area.config.slot_length / Interval(hours=1))
        return round((gauss_forecast / 1000) * w_to_wh_factor, 4)

    def event_market_cycle(self):
        self._decrease_price_timepoint_s = 0 * ureg.seconds

    def trigger_risk(self, new_risk: int = 0):
        new_risk = int(new_risk)
        if not (-1 < new_risk < 101):
            raise ValueError("'new_risk' value has to be in range 0 - 100")
        self.risk = new_risk
        self.log.warn("Risk changed to %s", new_risk)
