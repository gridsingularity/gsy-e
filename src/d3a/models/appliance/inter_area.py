"""
Copyright 2018 Grid Singularity
This file is part of D3A.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
from d3a.models.appliance.simple import SimpleAppliance
from d3a.d3a_core.util import make_iaa_name


class InterAreaAppliance(SimpleAppliance):
    parameters = ('area', 'owner')

    def __init__(self, area, owner):
        super().__init__()
        self.area = area
        self.owner = owner
        self.own_name = make_iaa_name(self.owner)
        self.own_market = None
        self.area_market = None

    def event_tick(self):
        if not self.own_market:
            self.own_market = self.owner.current_market
            if not self.own_market:
                # no market yet
                return
        if not self.area_market:
            self.area_market = self.area.current_market
        self.owner.stats.report_accounting(
            self.own_market,
            self.own_name,
            self.slot_energy(self.own_market) / self.area.config.ticks_per_slot,
            self.owner.now
        )
        self.area.stats.report_accounting(
            self.area_market,
            self.own_name,
            -1 * self.slot_energy(self.area_market) / self.area.config.ticks_per_slot,
            self.area.now
        )

    def slot_energy(self, market):
        energy = sum(
            t.offer.energy * (1 if t.seller == self.own_name else -1)
            for t in market.trades
            if self.own_name in (t.buyer, t.seller)
        )
        return energy
