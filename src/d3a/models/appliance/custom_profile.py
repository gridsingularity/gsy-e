from d3a.models.appliance.simple import SimpleAppliance


class CustomProfileAppliance(SimpleAppliance):
    def __init__(self):
        super().__init__()
        self.excess = 0.0

    def _slot_changed(self):
        market = self.owner.current_market
        if not market:
            return
        strategy = self.owner.strategy
        total_excess = strategy.bought[market.time_slot] - strategy.slot_load[market.time_slot]
        if total_excess < 0:
            self.log.warning("Could not buy enough energy, missing {} kW".format(total_excess))
        self.excess = total_excess / self.area.config.ticks_per_slot

    def event_activate(self):
        self._slot_changed()

    def event_market_cycle(self):
        self._slot_changed()

    def report_energy(self, energy):
        super().report_energy(energy - self.excess)
