from d3a.models.strategy.load_hours_fb import LoadHoursStrategy
from d3a.models.strategy.const import ConstSettings

"""
Example file for CustomLoadStrategy.
Is also used for integrationtest.
"""


class CustomLoadStrategy(LoadHoursStrategy):

    def update_posted_bids(self, market):
        """
        Copy of original code
        """
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
