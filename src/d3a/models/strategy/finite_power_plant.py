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
from pendulum import duration
from d3a.models.strategy.commercial_producer import CommercialStrategy
from d3a.models.read_user_profile import read_arbitrary_profile, InputProfileTypes
from d3a_interface.device_validator import validate_finite_diesel_generator


class FinitePowerPlant(CommercialStrategy):
    parameters = ('energy_rate', 'max_available_power_kW', )

    def __init__(self, energy_rate=None, max_available_power_kW=None):
        validate_finite_diesel_generator(max_available_power_kW=max_available_power_kW)
        super().__init__(energy_rate=energy_rate)
        self.max_available_power_kW = max_available_power_kW

    def event_activate(self):
        super().event_activate()
        self.max_available_power_kW = \
            read_arbitrary_profile(InputProfileTypes.IDENTITY, self.max_available_power_kW)

    def event_trade(self, *, market_id, trade):
        # Disable offering more energy than the initial offer, in order to adhere to the max
        # available power.
        pass

    def event_market_cycle(self):
        self.energy_per_slot_kWh = self.max_available_power_kW[self.area.next_market.time_slot] / \
            (duration(hours=1) / self.area.config.slot_length)
        if self.energy_per_slot_kWh <= 0.0:
            return
        super().event_market_cycle()
