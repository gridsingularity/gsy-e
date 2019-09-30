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
from d3a.models.appliance.base import BaseAppliance


class SimpleAppliance(BaseAppliance):
    """Example appliance that reports the traded energy in increments each tick"""

    def __init__(self):
        super().__init__()
        self._market_energy = {}

    def event_tick(self):
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
                self.owner.name, energy,
                self.area.now
            )
