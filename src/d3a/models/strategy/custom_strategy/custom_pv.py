from d3a.models.strategy.pv import PVStrategy


class CustomPvStrategy(PVStrategy):

    def produced_energy_forecast_kWh(self):
        """
        Overwrites d3a.models.strategy.pv.produced_energy_forecast_kWh
        Is called on every ACTIVATE event.
        :return: dictionary that describes Energy production in kWh for each market slot:
                 self.energy_production_forecast_kWh
                 len(self.energy_production_forecast_kWh.keys) = slot_count
        """

        pass

    def calculate_initial_sell_rate(self, current_time_h):
        """
        Overrides d3a.models.strategy.update_frequency.calculate_initial_sell_rate
        Is called on every MARKET_CYCLE event.
        Returns the initial value of the sell energy rate for each hour of the simulation
        :param current_time_h: slot time in hours (e.g. market.time_slot.hour)
        :return: energy rate
                 e.g.: self.area.config.market_maker_rate[current_time_h]
        """

        pass

    def decrease_energy_price_over_ticks(self, market):
        """
        Overrides d3a.models.strategy.update_frequency.decrease_energy_price_over_ticks
        Is called on every EVENT_TICK event.
        Should be used to modify the price decrease over the ticks for the selected market.
        """

        pass
