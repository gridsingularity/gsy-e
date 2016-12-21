from d3a.models.appliance.base import BaseAppliance
from d3a.models.area import Area


class SimpleAppliance(BaseAppliance):
    """Example appliance that reports the traded energy in increments each tick"""
    def event_tick(self, *, area: Area):
        if not self.owner:
            # Should not happen
            return
        market = area.current_market
        if not market:
            # No current market yet
            return
        # Fetch traded energy for `market`
        energy = self.owner.strategy.energy_balance(market)
        if energy:
            area.report_accounting(market, self.owner.name, energy / area.config.ticks_per_slot)
