from cached_property import cached_property

from d3a.models.appliance.simple import SimpleAppliance
from d3a.util import make_iaa_name


class InterAreaAppliance(SimpleAppliance):
    def __init__(self, area, owner):
        super().__init__()
        self.area = area
        self.owner = owner
        self.own_name = make_iaa_name(self.owner)
        self.own_market = None
        self.area_market = None

    def event_tick(self, *, area):
        if not self.own_market:
            self.own_market = self.owner.current_market
            if not self.own_market:
                # no market yet
                return
        if not self.area_market:
            self.area_market = self.area.current_market
        energy = self.slot_energy
        self.owner.report_accounting(
            self.own_market,
            self.own_name,
            energy / self.area.config.ticks_per_slot
        )
        self.area.report_accounting(
            self.area_market,
            self.own_name,
            -1 * energy / self.area.config.ticks_per_slot
        )

    @cached_property
    def slot_energy(self):
        energy = sum(
            t.offer.energy * (1 if t.seller == self.own_name else -1)
            for t in self.own_market.trades
            if self.own_name in (t.buyer, t.seller)
        )
        return energy
