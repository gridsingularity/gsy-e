from enum import Enum
from cached_property import cached_property

from d3a.models.strategy import ureg
from d3a.exceptions import MarketException
from d3a.models.strategy.const import ConstSettings


class InitialRateOptions(Enum):
    HISTORICAL_AVG_RATE = 1
    MARKET_MAKER_RATE = 2


class RateDecreaseOption(Enum):
    PERCENTAGE_BASED_ENERGY_RATE_DECREASE = 1
    CONST_ENERGY_RATE_DECREASE_PER_UPDATE = 2


class BidUpdateFrequencyMixin:
    def __init__(self,
                 initial_rate,
                 final_rate):
        self._initial_rate = initial_rate
        self._final_rate = final_rate
        self._increase_rate_timepoint_s = 0

    @cached_property
    def _increase_frequency_s(self):
        return self.area.config.tick_length.seconds * ConstSettings.MAX_OFFER_TRAVERSAL_LENGTH + 1

    def post_first_bid(self, market, energy_Wh):
        return self.post_bid(
            market,
            energy_Wh * self._initial_rate / 1000.0,
            energy_Wh / 1000.0
        )

    def update_market_cycle_bids(self, final_rate=None):
        if final_rate is not None:
            self._final_rate = final_rate
        self._increase_rate_timepoint_s = 0

    def update_posted_bids(self, market):
        # Decrease the selling price over the ticks in a slot
        current_tick_number = self.area.current_tick % self.area.config.ticks_per_slot
        elapsed_seconds = current_tick_number * self.area.config.tick_length.seconds
        if (
                # FIXME: Make sure that the offer reached every system participant.
                # FIXME: Therefore it can only be update (depending on number of niveau and
                # FIXME: InterAreaAgent min_offer_age
                current_tick_number > ConstSettings.MAX_OFFER_TRAVERSAL_LENGTH
                and elapsed_seconds > self._increase_rate_timepoint_s
        ):
            self._increase_rate_timepoint_s += self._increase_frequency_s
            existing_bids = list(self.get_posted_bids(market))
            for bid in existing_bids:
                market.delete_bid(bid.id)
                self.remove_bid_from_pending(bid.id, market)
                self.post_bid(market,
                              bid.energy * self._get_current_energy_rate(current_tick_number),
                              bid.energy)

    def _get_current_energy_rate(self, current_tick):
        percentage_of_rate = current_tick / self.area.config.ticks_per_slot
        return (self._final_rate - self._initial_rate) * percentage_of_rate + self._initial_rate


class OfferUpdateFrequencyMixin:

    def __init__(self,
                 initial_rate_option,
                 energy_rate_decrease_option,
                 energy_rate_decrease_per_update
                 ):
        self.initial_rate_option = InitialRateOptions(initial_rate_option)
        self.energy_rate_decrease_option = RateDecreaseOption(energy_rate_decrease_option)
        self.energy_rate_decrease_per_update = energy_rate_decrease_per_update
        self._decrease_price_timepoint_s = 0 * ureg.seconds
        self._decrease_price_every_nr_s = 0 * ureg.seconds
        self.min_selling_rate = 0

    def update_on_activate(self):
        self._decrease_price_every_nr_s = \
            (self.area.config.tick_length.seconds * ConstSettings.MAX_OFFER_TRAVERSAL_LENGTH + 1)\
            * ureg.seconds

    def calculate_initial_sell_rate(self, current_time_h):
        if self.initial_rate_option is InitialRateOptions.HISTORICAL_AVG_RATE:
            if self.area.historical_avg_rate == 0:
                return self.area.config.market_maker_rate[current_time_h]
            else:
                return self.area.historical_avg_rate
        elif self.initial_rate_option is InitialRateOptions.MARKET_MAKER_RATE:
            return self.area.config.market_maker_rate[current_time_h]
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
            next_market = list(self.area.markets.values())[0]
            self._decrease_offer_price(next_market,
                                       self._calculate_price_decrease_rate(next_market))

    def _decrease_offer_price(self, market, decrease_rate_per_tick):
        if market not in self.offers.open.values():
            return

        for offer, iterated_market in self.offers.open.items():
            if iterated_market != market:
                continue
            try:
                iterated_market.delete_offer(offer.id)
                new_offer = iterated_market.offer(
                    (offer.price - (offer.energy *
                                    decrease_rate_per_tick)),
                    offer.energy,
                    self.owner.name
                )
                if (new_offer.price/new_offer.energy) < self.min_selling_rate:
                    new_offer.price = self.min_selling_rate * new_offer.energy
                self.offers.replace(offer, new_offer, iterated_market)
            except MarketException:
                continue

    def _calculate_price_decrease_rate(self, market):
        if self.energy_rate_decrease_option is \
                RateDecreaseOption.PERCENTAGE_BASED_ENERGY_RATE_DECREASE:
            price_dec_per_slot = self.calculate_initial_sell_rate(market.time_slot_str) * \
                                 (1 - self.risk/ConstSettings.MAX_RISK)
            price_updates_per_slot = int(self.area.config.slot_length.seconds
                                         / self._decrease_price_every_nr_s.m)
            price_dec_per_update = price_dec_per_slot / price_updates_per_slot
            return price_dec_per_update
        elif self.energy_rate_decrease_option is \
                RateDecreaseOption.CONST_ENERGY_RATE_DECREASE_PER_UPDATE:
            return self.energy_rate_decrease_per_update

    def update_market_cycle_offers(self, min_selling_rate):
        self.min_selling_rate = min_selling_rate
        self._decrease_price_timepoint_s = self._decrease_price_every_nr_s
