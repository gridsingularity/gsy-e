from d3a.models.strategy.load_hours_fb import LoadHoursStrategy

"""
Example file for CustomLoadStrategy.
Is also used for integrationtest.
"""


class CustomLoadStrategy(LoadHoursStrategy):

    def update_posted_bids_over_ticks(self, market):
        """
        Copy of original code
        """
        # Decrease the selling price over the ticks in a slot
        current_tick_number = self.area.current_tick % self.area.config.ticks_per_slot
        elapsed_seconds = current_tick_number * self.area.config.tick_length.seconds
        if elapsed_seconds > self._increase_rate_timepoint_s:
            self._increase_rate_timepoint_s += self._increase_frequency_s
            existing_bids = list(self.get_posted_bids(market))
            for bid in existing_bids:
                if bid.id in market.bids.keys():
                    bid = market.bids[bid.id]
                market.delete_bid(bid.id)
                self.remove_bid_from_pending(bid.id, market)
                self.post_bid(market,
                              bid.energy * self._get_current_energy_rate(current_tick_number,
                                                                         market),
                              bid.energy)
