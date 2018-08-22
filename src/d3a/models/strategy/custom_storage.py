from d3a.models.strategy.storage import StorageStrategy


class CustomStorageStrategy(StorageStrategy):

    def calculate_energy_to_buy(self, energy):
        """
        Runs on
        :param energy:  initial energy that has to be clamped by this function
        :return: energy in kWh
        """

        pass

    def calculate_energy_to_sell(self, energy, target_market):
        """
        Runs every time sell_energy is run (on every EVENT_MARKET_CYCLE event)
        :param energy: initial energy that has to be clamped by this function
        :param target_market: target market object
        :return: energy in kWh
        """

        pass

    def calculate_selling_rate(self, market):
        """
        Calculate amount of energy that can be sold (considering SOC and market business startegy)
        :param market: market object
        :return: selling rat ein ct./kWh
        """

        pass

    def decrease_energy_price_over_ticks(self):
        """
        Overrides d3a.models.strategy.update_frequency.decrease_energy_price_over_ticks
        Is called on every EVENT_TICK event.
        Should be used to modify the price decrease over the ticks for the selected market.
        """

        pass

    def select_market_to_sell(self):
        """
        Runs every time sell_energy is run (on every EVENT_MARKET_CYCLE event)
        Return target market
        :return: market object
        """

        pass
