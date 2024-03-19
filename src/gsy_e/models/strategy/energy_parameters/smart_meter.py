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
from gsy_framework.utils import find_object_of_same_weekday_and_time
from pendulum.datetime import DateTime

from gsy_e.gsy_e_core.exceptions import GSyException
from gsy_e.models.strategy.state import SmartMeterState
from gsy_e.models.strategy import utils
from gsy_e.models.strategy.profile import profile_factory


class SmartMeterEnergyParameters:
    """Manage energy parameters for the Smart Meter Strategy class."""
    def __init__(self, smart_meter_profile,
                 smart_meter_profile_uuid: str = None,
                 smart_meter_measurement_uuid: str = None):
        self._energy_profile = profile_factory(smart_meter_profile, smart_meter_profile_uuid)
        self._measurement_profile = profile_factory(None, smart_meter_measurement_uuid)

        self._state = SmartMeterState()
        self._simulation_start_timestamp = None
        self._area = None

    def read_and_rotate_profiles(self):
        """Read and rotate all profiles"""
        self._energy_profile.read_or_rotate_profiles()
        self._measurement_profile.read_or_rotate_profiles()

    def activate(self, area):
        """Trigger by strategy activate event, configure the energy parameters for trading."""
        self._area = area
        self.read_and_rotate_profiles()
        self._simulation_start_timestamp = area.now

    def decrement_energy_requirement(self, energy_kWh: float, time_slot: DateTime, area_name: str):
        """Decrease the energy requirements of the asset."""
        self._state.decrement_energy_requirement(
            purchased_energy_Wh=energy_kWh * 1000,
            time_slot=time_slot,
            area_name=area_name)

    def set_energy_forecast_for_future_markets(self, time_slots, reconfigure: bool = True):
        """Set the energy consumption/production expectations for the upcoming market slots.

        Args:
            reconfigure: if True, re-read and preprocess the raw profile data.
        """
        if not self._energy_profile.profile:
            raise GSyException(
                f"Smart Meter {self._area.name} tries to set its required energy forecast without "
                "a profile.")

        for slot_time in time_slots:
            energy_kWh = find_object_of_same_weekday_and_time(
                self._energy_profile.profile, slot_time)
            # For the Smart Meter, the energy amount can be either positive (consumption) or
            # negative (production).
            consumed_energy = energy_kWh if energy_kWh > 0 else 0.0
            # Turn energy into a positive number (required for set_available_energy method)
            produced_energy = abs(energy_kWh) if energy_kWh < 0 else 0.0

            if consumed_energy and produced_energy:
                raise InconsistentEnergyException(
                    "The Smart Meter can't both produce and consume energy at the same time.")

            # NOTE: set_desired_energy accepts energy in Wh (not kWh) so we multiply * 1000
            self._state.set_desired_energy(consumed_energy * 1000, slot_time, overwrite=False)
            self._state.set_available_energy(produced_energy, slot_time, reconfigure)
            self._state.update_total_demanded_energy(slot_time)

    def set_energy_measurement_kWh(self, time_slot: DateTime) -> None:
        """Set the (simulated) actual energy of the device in a market slot."""
        energy_forecast_kWh = self._state.get_energy_at_market_slot(time_slot)
        simulated_measured_energy_kWh = utils.compute_altered_energy(energy_forecast_kWh)
        # This value can be either positive (consumption) or negative (production). This is
        # different from the other devices (PV, Load) where the value is positive regardless of
        # its direction (consumption or production)
        self._state.set_energy_measurement_kWh(simulated_measured_energy_kWh, time_slot)

    def reset(self, **kwargs):
        """Reconfigure energy parameters."""
        if kwargs.get("smart_meter_profile") is not None:
            self._energy_profile.input_profile = kwargs["smart_meter_profile"]
            self.set_energy_forecast_for_future_markets(kwargs["time_slots"], reconfigure=True)

    def serialize(self):
        """Create dict with smart meter energy parameters."""
        return {
            "smart_meter_profile": self._energy_profile.input_profile,
            "smart_meter_profile_uuid": self._energy_profile.input_profile_uuid
        }


class InconsistentEnergyException(Exception):
    """Exception raised when the energy produced/consumed by the Smart Meter doesn't make sense."""
