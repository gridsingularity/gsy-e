from pendulum import duration
from d3a.models.strategy import ureg, Q_
from d3a.models.strategy.commercial_producer import CommercialStrategy


class FinitePowerPlant(CommercialStrategy):
    parameters = ('energy_rate', 'max_available_power_kW', )

    def __init__(self, energy_rate=None, max_available_power_kW=None):
        super().__init__(energy_rate=energy_rate)
        self.max_available_power_kW = self._sanitize_max_available_power(max_available_power_kW)

    @staticmethod
    def _sanitize_max_available_power(max_available_power_kW):
        if isinstance(max_available_power_kW, int) or isinstance(max_available_power_kW, float):
            max_available_power_kW = {i: Q_(max_available_power_kW, ureg.kW) for i in range(24)}
        elif isinstance(max_available_power_kW, dict):
            latest_entry = Q_(0, ureg.kW)
            for i in range(24):
                if i not in max_available_power_kW:
                    max_available_power_kW[i] = Q_(latest_entry.m, ureg.kW)
                else:
                    latest_entry = Q_(max_available_power_kW[i], ureg.kW)
                    max_available_power_kW[i] = latest_entry
        else:
            raise ValueError("Max available power should either be a numerical value, "
                             "or an hourly dict of tuples.")
        if not all(float(power.m) >= 0.0 for power in max_available_power_kW.values()):
            raise ValueError("Max available power should be positive.")
        return max_available_power_kW

    def _markets_to_offer_on_activate(self):
        return list(self.area.markets.values())[:-1]

    def event_activate(self):
        self.energy_per_slot_kWh = ureg.kWh * \
            self.max_available_power_kW[0].m / (duration(hours=1) / self.area.config.slot_length)
        if self.energy_per_slot_kWh.m <= 0.0:
            return
        super().event_activate()

    def event_trade(self, *, market_id, trade):
        # Disable offering more energy than the initial offer, in order to adhere to the max
        # available power.
        pass

    def event_market_cycle(self):
        target_market_time = list(self.area.markets.keys())[-1]
        self.energy_per_slot_kWh = ureg.kWh * \
            self.max_available_power_kW[target_market_time.hour].m / \
            (duration(hours=1) / self.area.config.slot_length)
        if self.energy_per_slot_kWh.m <= 0.0:
            return
        super().event_market_cycle()
