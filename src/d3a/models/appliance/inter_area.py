from cached_property import cached_property
from collections import defaultdict

from d3a.models.appliance.simple import SimpleAppliance
from d3a.util import make_iaa_name


class InterAreaAppliance(SimpleAppliance):
    def __init__(self):
        super().__init__()
        self.market = None
        self.reported = False

    def event_tick(self, *, area):
        if not self.market:
            if not self.owner:
                # Should not happen
                return

            market = area.current_market
            if not market:
                # No current market yet
                return
            self.market = market
        self.report_energy()

    def report_energy(self):
        if self.reported:
            return
        for actor, energy in self.slot_energy.items():
            tick_energy = energy  # / self.area.config.ticks_per_slot
            self.area.report_accounting(
                self.market,
                actor,
                tick_energy
            )
        self.reported = True

    @cached_property
    def slot_energy(self):
        own_name = make_iaa_name(self.owner)
        higher_name = make_iaa_name(self.area)
        rv = defaultdict(int)
        for iaa in self.area.inter_area_agents[self.market]:
            if iaa.name != own_name:
                continue

            rv[own_name] += sum(
                -t.offer.energy
                for t in self.market.trades
                if t.buyer == own_name
            )

            rv[higher_name] += sum(
                t.offer.energy
                for t in self.market.trades
                if t.buyer == own_name and t.seller == higher_name
            )
        return rv
