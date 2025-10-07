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

from gsy_framework.read_user_profile import UserProfileReader, InputProfileTypes
from gsy_e.models.strategy.storage import StorageStrategy


class ElectrolyzerStrategy(StorageStrategy):

    def __init__(
        self,
        discharge_profile,
        conversion_factor_kg_to_kWh: float = 50.0,
        reservoir_capacity_kg: float = 56.0,
        reservoir_initial_capacity_kg: float = 5.6,
        production_rate_kg_h: float = 1.0,
    ):

        initial_capacity_kWh = reservoir_initial_capacity_kg * conversion_factor_kg_to_kWh
        capacity_kWh = reservoir_capacity_kg * conversion_factor_kg_to_kWh
        production_rate_kW = production_rate_kg_h * conversion_factor_kg_to_kWh
        initial_soc = (initial_capacity_kWh / capacity_kWh) * 100

        super().__init__(
            initial_soc=initial_soc,
            battery_capacity_kWh=capacity_kWh,
            max_abs_battery_power_kW=production_rate_kW,
            initial_buying_rate=31,
            final_buying_rate=31,
            final_selling_rate=32,
            initial_selling_rate=32,
        )

        self.discharge_profile = discharge_profile
        self.conversion_factor_kWh_kg = conversion_factor_kg_to_kWh
        self.load_profile_kWh = {}

    def event_activate(self, **kwargs):
        super().event_activate()

        load_profile_raw_kg = UserProfileReader().read_arbitrary_profile(
            InputProfileTypes.IDENTITY, self.discharge_profile
        )

        for key, value in load_profile_raw_kg.items():
            self.load_profile_kWh[key] = value * self.conversion_factor_kWh_kg

    def _sell_energy_to_spot_market(self):
        pass

    def event_market_cycle(self):
        super().event_market_cycle()
        current_market = self.area.spot_market

        energy_to_sell = self.state.get_available_energy_to_sell_kWh(current_market.time_slot)
        if (energy_to_sell - self.load_profile_kWh[current_market.time_slot]) >= 0:
            self.state._used_storage -= self.load_profile_kWh[current_market.time_slot]
            self.state.check_state(current_market.time_slot)
        else:
            requested_h2_kg = (
                self.load_profile_kWh[current_market.time_slot] / self.conversion_factor_kWh_kg
            )
            raise Exception(
                f"[{current_market.time_slot}]The Electrolyzer storage is not charged "
                f"properly. The customer requested {requested_h2_kg} kg but only "
                f"{self.state.used_storage/self.conversion_factor_kWh_kg} kg "
                f"are available"
            )
