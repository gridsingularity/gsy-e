from d3a.models.appliance.base import BaseAppliance


class SimpleAppliance(BaseAppliance):
    """Example appliance that reports the traded energy in increments each tick"""

    def __init__(self):
        super().__init__()
        self._market_energy = {}

    def event_tick(self, *, area):
        if not self.owner:
            # Should not happen
            return
        market = self.area.current_market
        if not market:
            # No current market yet
            return
        # Fetch traded energy for `market`
        energy = self._market_energy.get(market)
        if energy is None:
            energy = self._market_energy[market] = self.owner.strategy.energy_balance(market)
        self.report_energy(energy / self.area.config.ticks_per_slot)

    def report_energy(self, energy):
        if energy:
            self.area.stats.report_accounting(
                self.area.current_market,
                self.owner.name, energy
            )
