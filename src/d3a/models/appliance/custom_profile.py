from d3a.models.appliance.simple import SimpleAppliance


class CustomProfileAppliance(SimpleAppliance):
    def __init__(self):
        super().__init__()
        self.excess = 0.0

    def event_market_cycle(self):
        market = self.owner.current_market
        if not market:
            return
        strategy = self.owner.strategy
        self.excess = (strategy.bought[market.time_slot] -
                       strategy.slot_load[market.time_slot]) / self.area.config.ticks_per_slot

    def report_energy(self, energy):
        super().report_energy(energy - self.excess)
