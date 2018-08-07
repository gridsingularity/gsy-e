from enum import Enum

from d3a.models.strategy import ureg, Q_
from d3a.exceptions import MarketException
from d3a.models.strategy.const import ConstSettings


class InitialRateOptions(Enum):
    HISTORICAL_AVG_RATE = 1
    MARKET_MAKER_RATE = 2


class PriceDecreaseOption(Enum):
    PERCENTAGE_BASED_ENERGY_RATE_DECREASE = 1
    CONST_ENERGY_RATE_DECREASE_PER_UPDATE = 2


class OfferUpdateFrequencyMixin:

    def calculate_initial_sell_rate(self, current_time_h):
        if self.initial_rate_option is InitialRateOptions.HISTORICAL_AVG_RATE:
            if self.area.historical_avg_rate == 0:
                return Q_(self.area.config.market_maker_rate[current_time_h],
                          ureg.EUR_cents / ureg.kWh)
            else:
                return Q_(self.area.historical_avg_rate, ureg.EUR_cents / ureg.kWh)
        elif self.initial_rate_option is InitialRateOptions.MARKET_MAKER_RATE:
            return Q_(self.area.config.market_maker_rate[current_time_h],
                      ureg.EUR_cents / ureg.kWh)
        else:
            raise ValueError("Initial rate option should be one of the InitialRateOptions.")

    def decrease_energy_price_over_ticks(self):
        # Decrease the selling price over the ticks in a slot
        current_tick_number = self.area.current_tick % self.area.config.ticks_per_slot
        elapsed_seconds = current_tick_number * self.area.config.tick_length.seconds * ureg.seconds

        if (
                # FIXME: Make sure that the offer reached every system participant.
                # FIXME: Therefore it can only be update (depending on number of niveau and
                # FIXME: InterAreaAgent min_offer_age
                current_tick_number > ConstSettings.MAX_OFFER_TRAVERSAL_LENGTH
                and elapsed_seconds > self._decrease_price_timepoint_s
        ):
            self._decrease_price_timepoint_s += self._decrease_price_every_nr_s
            # print("Updating")
            next_market = list(self.area.markets.values())[0]
            # print("next_market: " + str(next_market))
            self.decrease_offer_price(next_market)

    def decrease_offer_price(self, market):
        if market not in self.offers.open.values():
            return

        for offer, iterated_market in self.offers.open.items():
            if iterated_market != market:
                continue
            # print("iterated_market: " + str(iterated_market))
            # print("iterated_market_hour: " + str(iterated_market.time_slot.hour))
            # print("Offers: " + str(offer))
            try:
                iterated_market.delete_offer(offer.id)
                new_offer = iterated_market.offer(
                    (offer.price - (offer.energy *
                                    self._calculate_price_decrease_rate(iterated_market))),
                    offer.energy,
                    self.owner.name
                )
                if (new_offer.price/new_offer.energy) < self.min_selling_rate.m:
                    new_offer.price = self.min_selling_rate.m * new_offer.energy
                self.offers.replace(offer, new_offer, iterated_market)
                # print("ESS Updated Rate: " + str(new_offer.price/new_offer.energy))
                self.log.info("[OLD RATE]: " + str(offer.price/offer.energy) +
                              " -> [NEW RATE]: " + str(new_offer.price/new_offer.energy))

            except MarketException:
                continue

    def _calculate_price_decrease_rate(self, market):
        if self.energy_rate_decrease_option is \
                PriceDecreaseOption.PERCENTAGE_BASED_ENERGY_RATE_DECREASE:
            price_dec_per_slot = self.calculate_initial_sell_rate(market.time_slot.hour).m * \
                                 (1 - self.risk/ConstSettings.MAX_RISK)
            price_updates_per_slot = int(self.area.config.slot_length.seconds
                                         / self._decrease_price_every_nr_s.m)
            price_dec_per_update = price_dec_per_slot / price_updates_per_slot
            # print("ESS price_dec_per_update: " + str(price_dec_per_update))
            return price_dec_per_update
        elif self.energy_rate_decrease_option is \
                PriceDecreaseOption.CONST_ENERGY_RATE_DECREASE_PER_UPDATE:
            return self.energy_rate_decrease_per_update

    # def produced_energy_forecast_real_data(self):
    #     # This forecast ist based on the real PV system data provided by enphase
    #     # They can be found in the tools folder
    #     # A fit of a gaussian function to those data results in a formula Energy(time)
    #     for slot_time in [
    #                 self.area.now + (self.area.config.slot_length * i)
    #                 for i in range(
    #                     (
    #                                 self.area.config.duration
    #                                 + (
    #                                         self.area.config.market_count *
    #                                         self.area.config.slot_length)
    #                     ) // self.area.config.slot_length)
    #                 ]:
    #         difference_to_midnight_in_minutes = slot_time.diff(self.midnight).in_minutes()
    #         self.energy_production_forecast_kWh[slot_time] =\
    #             self.gaussian_energy_forecast_kWh(difference_to_midnight_in_minutes)
    #         assert self.energy_production_forecast_kWh[slot_time] >= 0.0
    #
    # def gaussian_energy_forecast_kWh(self, time_in_minutes=0):
    #     # The sun rises at approx 6:30 and sets at 18hr
    #     # time_in_minutes is the difference in time to midnight
    #
    #     # Clamp to day range
    #     time_in_minutes %= 60 * 24
    #
    #     if (8 * 60) > time_in_minutes or time_in_minutes > (16.5 * 60):
    #         gauss_forecast = 0
    #
    #     else:
    #         gauss_forecast = 166.54 * math.exp(
    #             # time/5 is needed because we only have one data set per 5 minutes
    #
    #             (- (((round(time_in_minutes / 5, 0)) - 147.2)
    #                 / 38.60) ** 2
    #              )
    #         )
    #     # /1000 is needed to convert Wh into kW
    #     w_to_wh_factor = (self.area.config.slot_length / Interval(hours=1))
    #     return round((gauss_forecast / 1000) * w_to_wh_factor, 4)

    # def event_market_cycle(self):
    #     self._decrease_price_timepoint_s = self._decrease_price_every_nr_s
    #     # Iterate over all markets open in the future
    #     time = list(self.area.markets.keys())[0]
    #     market = list(self.area.markets.values())[0]
    #     market_time_h = market.time_slot.hour
    #     initial_sell_rate = self.calculate_initial_sell_rate(market_time_h)
    #     rounded_energy_rate = self._incorporate_rate_restrictions(initial_sell_rate,
    #                                                               market_time_h)
    #     # Sell energy and save that an offer was posted into a list
    #     if self.energy_production_forecast_kWh[time] != 0:
    #         offer = market.offer(
    #             rounded_energy_rate * self.panel_count *
    #             self.energy_production_forecast_kWh[time],
    #             self.energy_production_forecast_kWh[time] * self.panel_count,
    #             self.owner.name
    #         )
    #         self.offers.post(offer, market)
    #
    #     else:
    #         self.log.warn("PV has no forecast data for this time")

    # def trigger_risk(self, new_risk: int = 0):
    #     new_risk = int(new_risk)
    #     if not (-1 < new_risk < 101):
    #         raise ValueError("'new_risk' value has to be in range 0 - 100")
    #     self.risk = new_risk
    #     self.log.warn("Risk changed to %s", new_risk)
