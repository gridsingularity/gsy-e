from d3a.models.strategy.load_hours_fb import LoadHoursStrategy


class CustomLoadStrategy(LoadHoursStrategy):

    def update_posted_bids(self, market):
        """
        Overwrites d3a.models.strategy.load_hours_fb.update_posted_bids
        Is called on every TICK event.
        Should be used to modify the price of the bids over the ticks for the selected market.
        In the default implementation, an increase of the energy over the ticks is implemented
        """

        pass
