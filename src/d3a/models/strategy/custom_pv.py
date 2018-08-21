from d3a.models.strategy.pv import PVStrategy


class CustomPvStrategy(PVStrategy):

    def produced_energy_forecast_kWh(self):
        """
        Overwrites d3a.models.strategy.pv.produced_energy_forecast_real_data
        and returns the energy production of the custom PV for each market slot.
        Function is called on every ACTIVATE event.
        :return: dictionary that describes Energy production in kWh for each market slot:
                 self.energy_production_forecast_kWh
                 len(self.energy_production_forecast_kWh.keys) = slot_count
        """

        pass

    def calculate_initial_sell_rate(self, current_time_h):
        """
        Overrides d3a.models.strategy.update_frequency.calculate_initial_sell_rate
        and returns the initial value of the sell energy rate for each hour of the simulation
        Function is called on every MARKET_CYCLE event.
        :param current_time_h: slot time in hours (e.g. market.time_slot.hour)
        :return: energy rate
                 e.g.: self.area.config.market_maker_rate[current_time_h]
        """

        pass

    def decrease_energy_price_over_ticks(self):
        """
        Overrides d3a.models.strategy.update_frequency.decrease_energy_price_over_ticks
        and should be used to modify the price over the ticks for the selected market.
        Function is called on every EVENT_TICK event.
        :return: Nothing
        """

        pass
