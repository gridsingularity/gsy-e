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

import logging
from typing import List, Optional

from gsy_framework.exceptions import GSyException
from gsy_framework.utils import convert_W_to_Wh
from gsy_framework.validators.load_validator import LoadValidator
from gsy_framework.constants_limits import GlobalConfig
from pendulum import DateTime

import gsy_e.constants
from gsy_e.models.strategy import utils
from gsy_e.models.strategy.strategy_profile import profile_factory
from gsy_e.models.strategy.state import LoadState

log = logging.getLogger(__name__)


class LoadHoursEnergyParameters:
    """Basic energy parameters of the load strategy."""

    def __init__(self, avg_power_W, hrs_of_day=None):
        LoadValidator.validate_energy(avg_power_W=avg_power_W, hrs_of_day=hrs_of_day)

        self.state = LoadState()

        self.avg_power_W = avg_power_W

        # Energy consumed per market slot
        self.energy_per_slot_Wh = None

        # List of active hours of day (values range from 0 to 23)
        self.hrs_of_day: Optional[List[int]] = None
        self._area = None
        self._simulation_start_timestamp = None
        self._assign_hours_of_day(hrs_of_day)

    def serialize(self):
        """Return dict with the current energy parameter values."""
        return {"avg_power_W": self.avg_power_W, "hrs_of_day": self.hrs_of_day}

    def decrement_energy_requirement(
        self, energy_kWh: float, time_slot: DateTime, area_name: str
    ):
        """Decrease the energy requirements of the asset."""
        self.state.decrement_energy_requirement(
            purchased_energy_Wh=energy_kWh * 1000,
            time_slot=time_slot,
            area_name=area_name,
        )

    def set_energy_measurement_kWh(self, time_slot: DateTime) -> None:
        """Set the (simulated) actual energy consumed by the device in a market slot."""
        energy_forecast_kWh = self.state.get_desired_energy_Wh(time_slot) / 1000
        simulated_measured_energy_kWh = utils.compute_altered_energy(
            energy_forecast_kWh
        )

        self.state.set_energy_measurement_kWh(simulated_measured_energy_kWh, time_slot)

    def update_energy_requirement(self, time_slot):
        """Update the energy requirement and desired energy from the state class."""
        self.energy_per_slot_Wh = convert_W_to_Wh(
            self.avg_power_W, self._area.config.slot_length
        )
        if self.allowed_operating_hours(time_slot):
            desired_energy_Wh = self.energy_per_slot_Wh
        else:
            desired_energy_Wh = 0.0
        self.state.set_desired_energy(desired_energy_Wh, time_slot)

    def allowed_operating_hours(self, time_slot):
        """Check if timeslot inside allowed operating hours."""
        return time_slot.hour in self.hrs_of_day

    def event_activate_energy(self, area):
        """Update energy requirement upon the activation event."""
        self._area = area
        self._simulation_start_timestamp = area.now

    def reset(self, time_slot: DateTime, **kwargs):  # pylint: disable=unused-argument
        """Reset strategy parameters."""
        if kwargs.get("hrs_of_day") is not None:
            self._assign_hours_of_day(kwargs["hrs_of_day"])
        if kwargs.get("avg_power_W") is not None:
            self.avg_power_W = kwargs["avg_power_W"]

    def _get_day_of_timestamp(self, time_slot: DateTime):
        """Return the number of days passed from the simulation start date to the time slot."""
        if self._simulation_start_timestamp is None:
            return 0
        return (time_slot - self._simulation_start_timestamp).days

    def _assign_hours_of_day(self, hrs_of_day: List[int]):
        if hrs_of_day is None:
            hrs_of_day = list(range(24))

        self.hrs_of_day = hrs_of_day

        if not all(0 <= h <= 23 for h in hrs_of_day):
            raise ValueError(
                "Hrs_of_day list should contain integers between 0 and 23."
            )


class DefinedLoadEnergyParameters(LoadHoursEnergyParameters):
    """Energy parameters for the defined load strategy class."""

    def __init__(
        self,
        daily_load_profile=None,
        daily_load_profile_uuid: str = None,
        daily_load_measurement_uuid: str = None,
    ):
        super().__init__(avg_power_W=0, hrs_of_day=list(range(0, 24)))

        self.energy_profile = profile_factory(
            daily_load_profile, daily_load_profile_uuid
        )
        self.measurement_profile = profile_factory(None, daily_load_measurement_uuid)
        self.state = LoadState()

    def serialize(self):
        return {
            "daily_load_profile": self.energy_profile.input_profile,
            "daily_load_profile_uuid": self.energy_profile.input_profile_uuid,
            "daily_load_measurement_uuid": self.measurement_profile.input_profile_uuid,
        }

    def event_activate_energy(self, area):
        """
        Runs on activate event.
        :return: None
        """
        self.read_and_rotate_profiles()
        super().event_activate_energy(area)

    def reset(self, time_slot: DateTime, **kwargs) -> None:
        if kwargs.get("daily_load_profile") is not None:
            self.energy_profile.input_profile = kwargs["daily_load_profile"]
            self.energy_profile.read_or_rotate_profiles(reconfigure=True)

    def update_energy_requirement(self, time_slot):
        if not self.energy_profile.profile:
            if GlobalConfig.is_canary_network():
                return
            raise GSyException(
                "Load tries to set its energy forecasted requirement "
                "without a profile."
            )
        load_energy_kwh = self.energy_profile.get_value(time_slot)
        if load_energy_kwh is None:
            log.error(
                "Could not read area profile %s on timeslot %s. Configuration %s.",
                self.energy_profile.input_profile_uuid,
                time_slot,
                gsy_e.constants.CONFIGURATION_ID,
            )
            load_energy_kwh = 0.0
        self.state.set_desired_energy(
            load_energy_kwh * 1000, time_slot, overwrite=False
        )
        self.state.update_total_demanded_energy(time_slot)

    def _operating_hours(self, energy_kWh):
        """
        Disabled feature for this subclass
        """
        return 0

    def allowed_operating_hours(self, time_slot):
        """
        Disabled feature for this subclass
        """
        return True

    def read_and_rotate_profiles(self):
        """Read and rotate all profiles"""
        self.energy_profile.read_or_rotate_profiles()
        self.measurement_profile.read_or_rotate_profiles()


class LoadForecastExternalEnergyParamsMixin:
    """
    Energy parameters for LoadForecastExternalStrategy class. Mostly used to override / disable
    methods of the DefinedLoadEnergyParameters.
    """

    def read_or_rotate_profiles(self, reconfigure=False) -> None:
        """Overridden with empty implementation to disable reading profile from DB."""

    def event_activate_energy(self, area):
        """Overridden with empty implementation to disable profile activation."""


class LoadProfileForecastEnergyParams(
    LoadForecastExternalEnergyParamsMixin, DefinedLoadEnergyParameters
):
    """Energy parameters class for the forecasted external load profile strategy."""


class LoadHoursForecastEnergyParams(
    LoadForecastExternalEnergyParamsMixin, LoadHoursEnergyParameters
):
    """Energy parameters class for the forecasted external load hours strategy."""
