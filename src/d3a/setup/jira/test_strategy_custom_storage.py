from d3a.models.strategy.storage import StorageStrategy


class CustomStorageStrategy(StorageStrategy):

    def calculate_energy_to_buy(self, energy):
        """
        Copy of original code
        Greedy storage, as it buys maximal available and needed energy
        :return:
        """
        return self.state.clamp_energy_to_buy_kWh(energy)

    def calculate_energy_to_sell(self, energy, target_market):
        """
        Copy of original code
        """
        energy = self.state.clamp_energy_to_sell_kWh(energy, target_market.time_slot)
        return energy

    def calculate_selling_rate(self, market):
        """
        Return initial selling rate (market maker rate)
        """

        return self.area.config.market_maker_rate[market.time_slot.hour]

    def decrease_energy_price_over_ticks(self):
        """
        Decreases the offer rate by 0.1 ct/kWh per tick
        """

        decrease_rate_per_tick = 0.1
        # example for determining the current tick number:
        current_tick_number = self.area.current_tick % self.area.config.ticks_per_slot
        if current_tick_number >= 0:
            self._decrease_offer_price(self.area.next_market, decrease_rate_per_tick)

    def select_market_to_sell(self):
        """
        Sell on the most recent future market
        """
        return self.area.next_market
