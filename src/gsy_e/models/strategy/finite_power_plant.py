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

from typing import Union, Optional

from gsy_framework.read_user_profile import UserProfileReader, InputProfileTypes
from gsy_framework.utils import convert_str_to_pendulum_in_dict, convert_pendulum_to_str_in_dict
from gsy_framework.utils import get_from_profile_same_weekday_and_time, convert_kW_to_kWh
from gsy_framework.validators import FiniteDieselGeneratorValidator

from gsy_e.models.strategy.commercial_producer import CommercialStrategy


class FinitePowerPlant(CommercialStrategy):
    """Strategy class for finite power plant that can only sell a finite amount of energy."""

    def serialize(self):
        return {
            "energy_rate": self._sell_energy_profile.input_energy_rate,
            "max_available_power_kW": self.max_available_power_kW,
        }

    def __init__(
        self,
        max_available_power_kW: Union[float, dict, str],
        energy_rate: Optional[Union[float, dict, str]] = None,
    ):
        FiniteDieselGeneratorValidator.validate(max_available_power_kW=max_available_power_kW)
        super().__init__(energy_rate=energy_rate)
        self.max_available_power_kW = max_available_power_kW

    def event_activate(self, **kwargs):
        super().event_activate()
        self.max_available_power_kW = UserProfileReader().read_arbitrary_profile(
            InputProfileTypes.IDENTITY, self.max_available_power_kW
        )

    def event_offer_traded(self, *, market_id, trade):
        # Disable offering more energy than the initial offer, in order to adhere to the max
        # available power.
        pass

    def event_market_cycle(self):
        power_from_profile = get_from_profile_same_weekday_and_time(
            self.max_available_power_kW, self.area.spot_market.time_slot
        )
        self.energy_per_slot_kWh = convert_kW_to_kWh(
            power_from_profile, self.simulation_config.slot_length
        )
        if self.energy_per_slot_kWh <= 0.0:
            return
        super().event_market_cycle()

    def get_state(self):
        return {
            "energy_rate": convert_pendulum_to_str_in_dict(self._sell_energy_profile.profile),
            "max_available_power_kW": convert_pendulum_to_str_in_dict(self.max_available_power_kW),
        }

    def restore_state(self, saved_state):
        self._sell_energy_profile.profile = convert_str_to_pendulum_in_dict(
            saved_state["energy_rate"]
        )
        self.max_available_power_kW.update(
            convert_str_to_pendulum_in_dict(saved_state["max_available_power_kW"])
        )
