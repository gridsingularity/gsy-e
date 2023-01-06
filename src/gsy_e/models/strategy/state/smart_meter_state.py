"""
Copyright 2018 Grid Singularity
This file is part of Grid Singularity Exchange.

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
from typing import Dict

from pendulum import DateTime

from gsy_e.gsy_e_core.util import is_time_slot_in_past_markets
from gsy_e.models.strategy.state.base_states import (
    ConsumptionState, ProductionState, UnexpectedStateException)


class SmartMeterState(ConsumptionState, ProductionState):
    """State for the Smart Meter device."""

    @property
    def market_slots(self):
        """Return the market slots that have either available or required energy."""
        return self._available_energy_kWh.keys() | self._energy_requirement_Wh.keys()

    def delete_past_state_values(self, current_time_slot: DateTime):
        """Delete data regarding energy requirements and availability for past market slots."""
        to_delete = []
        for market_slot in self.market_slots:
            if is_time_slot_in_past_markets(market_slot, current_time_slot):
                to_delete.append(market_slot)

        for market_slot in to_delete:
            self._available_energy_kWh.pop(market_slot, None)
            self._energy_production_forecast_kWh.pop(market_slot, None)
            self._energy_requirement_Wh.pop(market_slot, None)
            self._desired_energy_Wh.pop(market_slot, None)

    def get_energy_at_market_slot(self, time_slot: DateTime) -> float:
        """Return the energy produced/consumed by the device at a specific market slot (in kWh).

        NOTE: The returned energy can either be negative (production) or positive (consumption).
        Therefore, pay attention when using its return values for strategy computations.
        """
        # We want the production energy to be a negative number (that's standard practice)
        produced_energy_kWh = -(abs(self.get_energy_production_forecast_kWh(time_slot, 0.0)))
        consumed_energy_kWh = self.get_desired_energy_Wh(time_slot, 0.0) / 1000
        if produced_energy_kWh and consumed_energy_kWh:
            raise UnexpectedStateException(
                f"{self} reported both produced and consumed energy at slot {time_slot}.")

        return produced_energy_kWh if produced_energy_kWh else consumed_energy_kWh

    def get_results_dict(self, current_time_slot: DateTime) -> dict:
        return {
            "smart_meter_profile_kWh": self.get_energy_at_market_slot(current_time_slot)
        }

    def to_dict(self, time_slot: DateTime) -> Dict:
        """Return a dict of the current stats of the smart meter according to timeslot."""
        return {
            "energy_requirement_kWh": self.get_energy_requirement_Wh(time_slot) / 1000.0,
            "available_energy_kWh": self.get_available_energy_kWh(time_slot)
        }
