from d3a.models.appliance.simple import SimpleAppliance


class CustomProfileAppliance(SimpleAppliance):
    def __init__(self):
        super().__init__()

    def _slot_changed(self):
        market = self.owner.current_market
        if not market:
            return
        strategy = self.owner.strategy
        missing = strategy.slot_load[market.time_slot] - strategy.bought[market.time_slot]
        if missing > 0:
            self.log.warning("Could not buy enough energy, missing {} kW".format(missing))

    def event_activate(self):
        self._slot_changed()

    def event_market_cycle(self):
        self._slot_changed()
