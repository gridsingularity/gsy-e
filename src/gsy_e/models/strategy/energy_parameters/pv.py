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
import math
import pathlib

import pendulum
from gsy_framework.read_user_profile import InputProfileTypes, read_arbitrary_profile
from gsy_framework.utils import convert_kW_to_kWh, key_in_dict_and_not_none
from gsy_framework.validators import PVValidator
from gsy_framework.constants_limits import GlobalConfig
from pendulum.datetime import DateTime

import gsy_e.constants
from gsy_e.gsy_e_core.exceptions import GSyException
from gsy_e.gsy_e_core.util import gsye_root_path
from gsy_e.models.strategy import utils
from gsy_e.models.strategy.strategy_profile import profile_factory
from gsy_e.models.strategy.state import PVState

log = logging.getLogger(__name__)


class PVEnergyParameters:
    """Energy parameters for the PV strategy with gaussian generation profile."""
    def __init__(self, panel_count: int = 1, capacity_kW: float = None):
        PVValidator.validate_energy(panel_count=panel_count, capacity_kW=capacity_kW)

        self.panel_count = panel_count
        self.capacity_kW = capacity_kW
        self._state = PVState()

    def serialize(self):
        """Return dict with the current energy parameter values."""
        return {
            "panel_count": self.panel_count,
            "capacity_kW": self.capacity_kW
        }

    def activate(self, simulation_config):
        """Activate the energy parameters, called during the event_activate strategy event."""
        if self.capacity_kW is None:
            self.capacity_kW = simulation_config.capacity_kW

    def set_produced_energy_forecast(self, time_slot, slot_length, reconfigure=True):
        """Generate the energy forecast value for the specified timeslot."""
        difference_to_midnight_in_minutes = time_slot.diff(
            pendulum.datetime(
                time_slot.year, time_slot.month, time_slot.day)).in_minutes() % (60 * 24)
        available_energy_kWh = self._gaussian_energy_forecast_kWh(
            slot_length, difference_to_midnight_in_minutes) * self.panel_count
        self._state.set_available_energy(available_energy_kWh, time_slot, reconfigure)

    def reset(self, **kwargs):
        """Reset / update energy parameters."""
        if key_in_dict_and_not_none(kwargs, "panel_count"):
            self.panel_count = kwargs["panel_count"]
        if key_in_dict_and_not_none(kwargs, "capacity_kW"):
            self.capacity_kW = kwargs["capacity_kW"]

    def _gaussian_energy_forecast_kWh(self, slot_length, time_in_minutes=0):
        # The sun rises at approx 6:30 and sets at 18hr
        # time_in_minutes is the difference in time to midnight

        # Clamp to day range
        time_in_minutes %= 60 * 24

        if (8 * 60) > time_in_minutes or time_in_minutes > (16.5 * 60):
            gauss_forecast = 0

        else:
            gauss_forecast = self.capacity_kW * math.exp(
                # time/5 is needed because we only have one data set per 5 minutes

                (- (((round(time_in_minutes / 5, 0)) - 147.2)
                    / 38.60) ** 2
                 )
            )

        return round(convert_kW_to_kWh(gauss_forecast, slot_length), 4)

    def set_energy_measurement_kWh(self, time_slot: DateTime) -> None:
        """Set the (simulated) actual energy produced by the device in a market slot."""
        energy_forecast_kWh = self._state.get_energy_production_forecast_kWh(time_slot)
        simulated_measured_energy_kWh = utils.compute_altered_energy(energy_forecast_kWh)

        self._state.set_energy_measurement_kWh(simulated_measured_energy_kWh, time_slot)


class PVPredefinedEnergyParameters(PVEnergyParameters):
    """Energy-related parameters for the PVPredefinedStrategy class."""
    def __init__(self, panel_count: int = 1, cloud_coverage: int = None,
                 capacity_kW: float = None):
        super().__init__(panel_count, capacity_kW)
        self.cloud_coverage = cloud_coverage
        self._power_profile_index = cloud_coverage
        # in this strategy we do not use the StrategyProfile but populate a dictionary
        self.energy_profile = {}

    def serialize(self):
        return {
            **super().serialize(),
            "cloud_coverage": self.cloud_coverage
        }

    def read_predefined_profile_for_pv(self, simulation_config):
        """
        Reads profile data from the predefined power profiles. Reads config and constructor
        parameters and selects the appropriate predefined profile.
        """
        if self._power_profile_index is None or self._power_profile_index == 4:
            self._power_profile_index = 0
        if self._power_profile_index == 0:  # 0:sunny
            profile_path = (
                pathlib.Path(gsye_root_path + "/resources/Solar_Curve_sunny_normalized.csv"))
        elif self._power_profile_index == 1:  # 1:partial
            profile_path = (
                pathlib.Path(gsye_root_path + "/resources/Solar_Curve_partial_normalized.csv"))
        elif self._power_profile_index == 2:  # 2:cloudy
            profile_path = (
                pathlib.Path(gsye_root_path + "/resources/Solar_Curve_cloudy_normalized.csv"))
        else:
            raise ValueError("Energy_profile has to be in [0,1,2,4]")

        power_weight_profile = read_arbitrary_profile(
            InputProfileTypes.IDENTITY, profile_path)

        self.energy_profile = {
            time_slot: convert_kW_to_kWh(
                weight * self.capacity_kW, simulation_config.slot_length)
            for time_slot, weight in power_weight_profile.items()}

    def set_produced_energy_forecast_in_state(
            self, owner_name, time_slots, reconfigure=True):
        """Update the production energy forecast."""
        self._power_profile_index = self.cloud_coverage
        if not self.energy_profile:
            raise GSyException(
                f"PV {owner_name} tries to set its available energy forecast without a "
                "power profile.")
        for time_slot in time_slots:
            datapoint_kWh = self.energy_profile.get(time_slot)
            if datapoint_kWh is None:
                log.error("Could not read area %s profile on timeslot %s. Configuration %s.",
                          owner_name, time_slot, gsy_e.constants.CONFIGURATION_ID)
                datapoint_kWh = 0.0
            available_energy_kWh = datapoint_kWh * self.panel_count
            self._state.set_available_energy(available_energy_kWh, time_slot, reconfigure)

    def reconfigure(self, **kwargs):
        """Reconfigure the device properties at runtime using the provided arguments."""

        # kwargs["cloud_coverage"] = None is a valid value, therefore a None check should not
        # be added here.
        if "cloud_coverage" in kwargs:
            self.cloud_coverage = kwargs["cloud_coverage"]
            self._power_profile_index = self.cloud_coverage


class PVUserProfileEnergyParameters(PVEnergyParameters):
    """Energy-related parameters for the PVUserProfile Strategy class."""
    def __init__(self, panel_count: int = 1,
                 power_profile: str = None,
                 power_profile_uuid: str = None,
                 power_measurement_uuid: str = None):
        super().__init__(panel_count, None)
        self.energy_profile = profile_factory(power_profile, power_profile_uuid)
        self.measurement_profile = profile_factory(None, power_measurement_uuid)

    def serialize(self):
        return {
            **super().serialize(),
            "power_profile": self.energy_profile.input_profile,
            "power_profile_uuid": self.energy_profile.input_profile_uuid,
            "power_measurement_uuid": self.measurement_profile.input_profile_uuid
        }

    def read_predefined_profile_for_pv(self):
        """
        Reads profile data from the power profile. Handles csv files and dicts.
        :return: key value pairs of time to energy in kWh
        """
        self.energy_profile.read_or_rotate_profiles()
        self.measurement_profile.read_or_rotate_profiles()

    def reset(self, **kwargs):
        """Reset the energy parameters of the strategy."""
        if key_in_dict_and_not_none(kwargs, "power_profile"):
            self.energy_profile.input_profile = kwargs["power_profile"]
        self.energy_profile.read_or_rotate_profiles(reconfigure=True)

    def set_produced_energy_forecast_in_state(
            self, owner_name, time_slots, reconfigure=True):
        """Update the production energy forecast."""
        if not self.energy_profile.profile:
            if GlobalConfig.is_canary_network():
                return
            raise GSyException(
                f"PV {owner_name} tries to set its available energy forecast without a "
                "power profile.")
        for time_slot in time_slots:
            energy_from_profile_kWh = self.energy_profile.get_value(time_slot)
            if energy_from_profile_kWh is None:
                log.error("Could not read area %s profile on timeslot %s. Configuration %s.",
                          owner_name, time_slot, gsy_e.constants.CONFIGURATION_ID)
                energy_from_profile_kWh = 0.0

            available_energy_kWh = energy_from_profile_kWh * self.panel_count
            self._state.set_available_energy(available_energy_kWh, time_slot, reconfigure)
