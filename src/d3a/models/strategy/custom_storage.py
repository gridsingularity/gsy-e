from d3a.models.strategy.storage import StorageStrategy


class CustomStorageStrategy(StorageStrategy):

    def calculate_energy_to_buy(self, energy):
        """
        Is called by StorageStrategy.buy_energy and runs on every EVENT_TICK event
        Clamps to-buy energy to physical or market margins
        :param energy in kWh (initial energy that has to be clamped by this function)
        :return: energy in kWh
        """

        pass

    def calculate_energy_to_sell(self, energy, target_market):
        """
        Is called by StorageStrategy.sell_energy and runs on every EVENT_MARKET_CYCLE event
        Clamps to-sell energy to physical or market margins
        :param energy in kWh (initial energy that has to be clamped by this function)
        :param target_market: target market object
        :return: energy in kWh
        """

        pass

    def calculate_selling_rate(self, market):
        """
        Is called by StorageStrategy.sell_energy and runs on every EVENT_MARKET_CYCLE event
        Returns initial selling rate
        :param market: market object
        :return: selling rat ein ct./kWh
        """

        pass

    def decrease_energy_price_over_ticks(self):
        """
        Overrides d3a.models.strategy.update_frequency.decrease_energy_price_over_ticks
        Is called on every EVENT_TICK event
        Should be used to modify the price decrease over the ticks for the selected market.
        """

        pass

    def select_market_to_sell(self):
        """
        Is called by StorageStrategy.sell_energy and runs on every EVENT_MARKET_CYCLE event
        Returns target market object
        :return: market object
        """

        pass

    def update_posted_bids(self, market):
        """
        Overwrites d3a.models.strategy.load_hours_fb.update_posted_bids
        Is called on every TICK event.
        Should be used to modify the price of the bids over the ticks for the selected market.
        In the default implementation, an increase of the energy over the ticks is implemented
        :param market: market object
        """

        pass
