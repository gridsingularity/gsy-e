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
import pathlib

from gsy_framework.constants_limits import ConstSettings, GlobalConfig
from gsy_framework.read_user_profile import read_arbitrary_profile, InputProfileTypes
from gsy_framework.utils import convert_kW_to_kWh
from gsy_framework.utils import key_in_dict_and_not_none, find_object_of_same_weekday_and_time
from pendulum import duration

from gsy_e.gsy_e_core.exceptions import GSyException
from gsy_e.gsy_e_core.global_objects_singleton import global_objects
from gsy_e.gsy_e_core.util import d3a_path
from gsy_e.gsy_e_core.util import should_read_profile_from_db
from gsy_e.models.strategy.pv import PVStrategy, PVEnergyParameters


class PVPredefinedEnergyParameters(PVEnergyParameters):
    """Energy-related parameters for the PVPredefinedStrategy class."""
    def __init__(self, panel_count: int = 1, cloud_coverage: int = None,
                 capacity_kW: float = None):
        super().__init__(panel_count, capacity_kW)
        self.cloud_coverage = cloud_coverage
        self._power_profile_index = cloud_coverage
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
            if simulation_config.pv_user_profile is not None:
                self.energy_profile = simulation_config.pv_user_profile
                return
            self._power_profile_index = simulation_config.cloud_coverage
        if self._power_profile_index == 0:  # 0:sunny
            profile_path = (
                pathlib.Path(d3a_path + "/resources/Solar_Curve_sunny_normalized.csv"))
        elif self._power_profile_index == 1:  # 1:partial
            profile_path = (
                pathlib.Path(d3a_path + "/resources/Solar_Curve_partial_normalized.csv"))
        elif self._power_profile_index == 2:  # 2:cloudy
            profile_path = (
                pathlib.Path(d3a_path + "/resources/Solar_Curve_cloudy_normalized.csv"))
        else:
            raise ValueError("Energy_profile has to be in [0,1,2,4]")

        power_weight_profile = read_arbitrary_profile(
            InputProfileTypes.IDENTITY, profile_path)

        self.energy_profile = {
            time_slot: convert_kW_to_kWh(
                weight * self.capacity_kW, simulation_config.slot_length)
            for time_slot, weight in power_weight_profile.items()}

    def set_produced_energy_forecast_in_state(
            self, config_cloud_coverage, owner_name, time_slots, reconfigure=True):
        """Update the production energy forecast."""
        self._power_profile_index = self.cloud_coverage or config_cloud_coverage
        if not self.energy_profile:
            raise GSyException(
                f"PV {owner_name} tries to set its available energy forecast without a "
                "power profile.")
        for time_slot in time_slots:
            available_energy_kWh = find_object_of_same_weekday_and_time(
                self.energy_profile, time_slot) * self.panel_count
            self._state.set_available_energy(available_energy_kWh, time_slot, reconfigure)

    def reconfigure(self, **kwargs):
        """Reconfigure the device properties at runtime using the provided arguments."""
        if key_in_dict_and_not_none(kwargs, "cloud_coverage"):
            self.cloud_coverage = kwargs["cloud_coverage"]


class PVPredefinedStrategy(PVStrategy):
    """
        Strategy responsible for using one of the predefined PV profiles.
    """

    def __init__(
            self, panel_count: int = 1,
            initial_selling_rate: float = ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE,
            final_selling_rate: float = ConstSettings.PVSettings.SELLING_RATE_RANGE.final,
            cloud_coverage: int = None,
            fit_to_limit: bool = True,
            update_interval=None,
            energy_rate_decrease_per_update=None,
            use_market_maker_rate: bool = False,
            capacity_kW: float = None,
            ):
        """
        Constructor of PVPredefinedStrategy
        Args:
            panel_count: Number of solar panels for this PV plant
            initial_selling_rate: Upper Threshold for PV offers
            final_selling_rate: Lower Threshold for PV offers
            cloud_coverage: cloud conditions.
                                0=sunny,
                                1=partially cloudy,
                                2=cloudy,
                                4=use global profile
                                None=use global cloud_coverage (default)
            fit_to_limit: Linear curve following initial_selling_rate & final_selling_rate
            update_interval: Interval after which PV will update its offer
            energy_rate_decrease_per_update: Slope of PV Offer change per update
            capacity_kW: power rating of the predefined profiles
        """

        if update_interval is None:
            update_interval = \
                duration(minutes=ConstSettings.GeneralSettings.DEFAULT_UPDATE_INTERVAL)

        self._energy_params = PVPredefinedEnergyParameters(
            panel_count, cloud_coverage, capacity_kW)
        super().__init__(panel_count=panel_count,
                         initial_selling_rate=initial_selling_rate,
                         final_selling_rate=final_selling_rate,
                         fit_to_limit=fit_to_limit,
                         update_interval=update_interval,
                         energy_rate_decrease_per_update=energy_rate_decrease_per_update,
                         capacity_kW=capacity_kW,
                         use_market_maker_rate=use_market_maker_rate
                         )

    def read_config_event(self):
        # this is to trigger to read from self.simulation_config.cloud_coverage:
        self._energy_params.cloud_coverage = None
        self._energy_params.read_predefined_profile_for_pv(self.simulation_config)
        self.set_produced_energy_forecast_in_state(reconfigure=True)

    def set_produced_energy_forecast_in_state(self, reconfigure=True):
        """Update the production energy forecast."""
        time_slots = [self.area.spot_market.time_slot]
        if GlobalConfig.FUTURE_MARKET_DURATION_HOURS:
            time_slots.extend(self.area.future_market_time_slots)

        if reconfigure:
            self._energy_params.read_predefined_profile_for_pv(self.simulation_config)

        self._energy_params.set_produced_energy_forecast_in_state(
            self.simulation_config.cloud_coverage, self.owner.name, time_slots, reconfigure
        )

    def area_reconfigure_event(self, **kwargs):
        """Reconfigure the device properties at runtime using the provided arguments."""
        self._energy_params.reconfigure(**kwargs)
        super().area_reconfigure_event(**kwargs)


class PVUserProfileEnergyParameters(PVEnergyParameters):
    """Energy-related parameters for the PVUserProfile Strategy class."""
    def __init__(self, panel_count: int = 1, power_profile: str = None,
                 power_profile_uuid: str = None):
        super().__init__(panel_count, None)
        self.power_profile = None
        self.power_profile_uuid = power_profile_uuid

        if should_read_profile_from_db(power_profile_uuid):
            self._power_profile_input = None
        else:
            self._power_profile_input = power_profile
        self.energy_profile = {}

    def serialize(self):
        return {
            **super().serialize(),
            "power_profile": self.power_profile,
            "power_profile_uuid": self.power_profile_uuid
        }

    def _read_or_rotate_profiles(self, reconfigure=False):
        input_profile = (self._power_profile_input
                         if reconfigure or not self.power_profile else self.power_profile)
        if global_objects.profiles_handler.should_create_profile(
                self.energy_profile) or reconfigure:
            self.energy_profile = (
                global_objects.profiles_handler.rotate_profile(
                    profile_type=InputProfileTypes.POWER,
                    profile=input_profile,
                    profile_uuid=self.power_profile_uuid))

    def read_predefined_profile_for_pv(self):
        """
        Reads profile data from the power profile. Handles csv files and dicts.
        :return: key value pairs of time to energy in kWh
        """
        self._read_or_rotate_profiles()

    def reset(self, **kwargs):
        """Reset the energy parameters of the strategy."""
        if key_in_dict_and_not_none(kwargs, "power_profile"):
            self._power_profile_input = kwargs["power_profile"]
        self._read_or_rotate_profiles(reconfigure=True)

    def set_produced_energy_forecast_in_state(
            self, owner_name, time_slots, reconfigure=True):
        """Update the production energy forecast."""
        if not self.energy_profile:
            raise GSyException(
                f"PV {owner_name} tries to set its available energy forecast without a "
                "power profile.")
        for time_slot in time_slots:
            available_energy_kWh = find_object_of_same_weekday_and_time(
                self.energy_profile, time_slot) * self.panel_count
            self._state.set_available_energy(available_energy_kWh, time_slot, reconfigure)


class PVUserProfileStrategy(PVStrategy):
    """
        Strategy responsible for reading a profile in the form of a dict of values.
    """

    def __init__(
            self, power_profile=None, panel_count: int = 1,
            initial_selling_rate: float = ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE,
            final_selling_rate: float = ConstSettings.PVSettings.SELLING_RATE_RANGE.final,
            fit_to_limit: bool = True,
            update_interval=duration(
                minutes=ConstSettings.GeneralSettings.DEFAULT_UPDATE_INTERVAL),
            energy_rate_decrease_per_update=None,
            use_market_maker_rate: bool = False,
            power_profile_uuid: str = None):
        """
        Constructor of PVUserProfileStrategy
        Args:
            power_profile: input profile for a day. Can be either a csv file path,
                           or a dict with hourly data (Dict[int, float])
                           or a dict with arbitrary time data (Dict[str, float])
            panel_count: number of solar panels for this PV plant
            final_selling_rate: lower threshold for the PV sale price
        """
        self._energy_params = PVUserProfileEnergyParameters(
            panel_count, power_profile, power_profile_uuid)
        super().__init__(panel_count=panel_count,
                         initial_selling_rate=initial_selling_rate,
                         final_selling_rate=final_selling_rate,
                         fit_to_limit=fit_to_limit,
                         update_interval=update_interval,
                         energy_rate_decrease_per_update=energy_rate_decrease_per_update,
                         use_market_maker_rate=use_market_maker_rate)

    def set_produced_energy_forecast_in_state(self, reconfigure=True):
        time_slots = [self.area.spot_market.time_slot]
        if GlobalConfig.FUTURE_MARKET_DURATION_HOURS:
            time_slots.extend(self.area.future_market_time_slots)

        self._energy_params.set_produced_energy_forecast_in_state(
            self.owner.name, time_slots, reconfigure
        )

    def area_reconfigure_event(self, **kwargs):
        """Reconfigure the device properties at runtime using the provided arguments."""
        super().area_reconfigure_event(**kwargs)
        self._energy_params.reset(**kwargs)
        self.set_produced_energy_forecast_in_state(reconfigure=True)

    def event_market_cycle(self):
        self._energy_params.read_predefined_profile_for_pv()
        super().event_market_cycle()

    def event_activate_energy(self):
        self._energy_params.read_predefined_profile_for_pv()
        super().event_activate_energy()
