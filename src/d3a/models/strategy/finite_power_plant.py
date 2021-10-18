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
from d3a_interface.read_user_profile import read_arbitrary_profile, InputProfileTypes
from d3a_interface.utils import convert_str_to_pendulum_in_dict, convert_pendulum_to_str_in_dict
from d3a_interface.utils import find_object_of_same_weekday_and_time, convert_kW_to_kWh
from d3a_interface.validators import FiniteDieselGeneratorValidator

from d3a.models.strategy.commercial_producer import CommercialStrategy


class FinitePowerPlant(CommercialStrategy):
    parameters = ('energy_rate', 'max_available_power_kW', )

    def __init__(self, energy_rate=None, max_available_power_kW=None):
        FiniteDieselGeneratorValidator.validate(max_available_power_kW=max_available_power_kW)
        super().__init__(energy_rate=energy_rate)
        self.max_available_power_kW = max_available_power_kW

    def event_activate(self, **kwargs):
        super().event_activate()
        self.max_available_power_kW = \
            read_arbitrary_profile(InputProfileTypes.IDENTITY, self.max_available_power_kW)

    def event_offer_traded(self, *, market_id, trade):
        # Disable offering more energy than the initial offer, in order to adhere to the max
        # available power.
        pass

    def event_market_cycle(self):
        power_from_profile = \
            find_object_of_same_weekday_and_time(self.max_available_power_kW,
                                                 self.area.spot_market.time_slot)
        self.energy_per_slot_kWh = convert_kW_to_kWh(power_from_profile,
                                                     self.area.config.slot_length)
        if self.energy_per_slot_kWh <= 0.0:
            return
        super().event_market_cycle()

    def get_state(self):
        return {
            "energy_rate": convert_pendulum_to_str_in_dict(self.energy_rate),
            "max_available_power_kW": convert_pendulum_to_str_in_dict(
                self.max_available_power_kW)
        }

    def restore_state(self, saved_state):
        self.energy_rate.update(convert_str_to_pendulum_in_dict(saved_state["energy_rate"]))
        self.max_available_power_kW.update(convert_str_to_pendulum_in_dict(
            saved_state["max_available_power_kW"]))
