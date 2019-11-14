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
import pathlib

from pendulum import DateTime, duration
from d3a.d3a_core.util import generate_market_slot_list
from d3a.models.strategy.pv import PVStrategy
from d3a_interface.constants_limits import ConstSettings
from d3a.models.read_user_profile import read_arbitrary_profile, InputProfileTypes
from d3a.d3a_core.util import d3a_path
from typing import Dict

"""
Creates a PV that uses a profile as input for its power values, either predefined or provided
by the user.
"""


class PVPredefinedStrategy(PVStrategy):
    """
        Strategy responsible for using one of the predefined PV profiles.
    """
    parameters = ('panel_count', 'initial_selling_rate', 'final_selling_rate', 'cloud_coverage',
                  'fit_to_limit', 'update_interval', 'energy_rate_decrease_per_update',
                  'max_panel_power_W', 'use_market_maker_rate')

    def __init__(
            self, panel_count: int = 1,
            initial_selling_rate: float = ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE,
            final_selling_rate: float = ConstSettings.PVSettings.SELLING_RATE_RANGE.final,
            cloud_coverage: int = None,
            fit_to_limit: bool = True,
            update_interval=duration(
                minutes=ConstSettings.GeneralSettings.DEFAULT_UPDATE_INTERVAL),
            energy_rate_decrease_per_update:
            float = ConstSettings.GeneralSettings.ENERGY_RATE_DECREASE_PER_UPDATE,
            max_panel_power_W: float = None,
            use_market_maker_rate: bool = False):
        """
        Constructor of PVPredefinedStrategy
        :param panel_count: Number of solar panels for this PV plant
        :param initial_selling_rate: Upper Threshold for PV offers
        :param final_selling_rate: Lower Threshold for PV offers
        :param cloud_coverage: cloud conditions. 0=sunny, 1=partially cloudy, 2=cloudy
        :param fit_to_limit: Linear curve following initial_selling_rate & final_selling_rate
        :param update_interval: Interval after which PV will update its offer
        :param energy_rate_decrease_per_update: Slope of PV Offer change per update
        :param max_panel_power_W: Peak power per panel
        """

        super().__init__(panel_count=panel_count,
                         initial_selling_rate=initial_selling_rate,
                         final_selling_rate=final_selling_rate,
                         fit_to_limit=fit_to_limit,
                         update_interval=update_interval,
                         energy_rate_decrease_per_update=energy_rate_decrease_per_update,
                         max_panel_power_W=max_panel_power_W,
                         use_market_maker_rate=use_market_maker_rate
                         )
        self.cloud_coverage = cloud_coverage
        self._power_profile_index = cloud_coverage

    def produced_energy_forecast_kWh(self):
        # TODO: Need to have 2-stage initialization as well, because the area objects are not
        # created when the constructor is executed if we inherit from a mixin class,
        # therefore config cannot be read at that point
        self.read_config_event()

    def read_config_event(self):
        self._power_profile_index = self.cloud_coverage \
            if self.cloud_coverage is not None else self.area.config.cloud_coverage
        data = self._read_predefined_profile_for_pv()

        for slot_time in generate_market_slot_list(area=self.area):
            self.energy_production_forecast_kWh[slot_time] = \
                data[slot_time] * self.panel_count
            self.state.available_energy_kWh[slot_time] = \
                self.energy_production_forecast_kWh[slot_time]

    def _read_predefined_profile_for_pv(self) -> Dict[DateTime, float]:
        """
        Reads profile data from the predefined power profiles. Reads config and constructor
        parameters and selects the appropriate predefined profile.
        :return: key value pairs of time to energy in kWh
        """
        if self._power_profile_index is None or self._power_profile_index == 4:
            if self.owner.config.pv_user_profile is not None:
                return self.owner.config.pv_user_profile
            else:
                self._power_profile_index = self.owner.config.cloud_coverage
        if self._power_profile_index == 0:  # 0:sunny
            profile_path = pathlib.Path(d3a_path + '/resources/Solar_Curve_W_sunny.csv')
        elif self._power_profile_index == 1:  # 1:partial
            profile_path = pathlib.Path(d3a_path + '/resources/Solar_Curve_W_partial.csv')
        elif self._power_profile_index == 2:  # 2:cloudy
            profile_path = pathlib.Path(d3a_path + '/resources/Solar_Curve_W_cloudy.csv')
        else:
            raise ValueError("Energy_profile has to be in [0,1,2]")

        # Populate energy production forecast data
        return read_arbitrary_profile(
            InputProfileTypes.POWER, str(profile_path))


class PVUserProfileStrategy(PVPredefinedStrategy):
    """
        Strategy responsible for reading a profile in the form of a dict of values.
    """
    parameters = ('power_profile', 'panel_count', 'initial_selling_rate', 'final_selling_rate',
                  'fit_to_limit', 'update_interval', 'energy_rate_decrease_per_update',
                  'max_panel_power_W', 'use_market_maker_rate')

    def __init__(
            self, power_profile, panel_count: int = 1,
            initial_selling_rate: float = ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE,
            final_selling_rate: float = ConstSettings.PVSettings.SELLING_RATE_RANGE.final,
            fit_to_limit: bool = True,
            update_interval=duration(
                minutes=ConstSettings.GeneralSettings.DEFAULT_UPDATE_INTERVAL),
            energy_rate_decrease_per_update:
            float = ConstSettings.GeneralSettings.ENERGY_RATE_DECREASE_PER_UPDATE,
            max_panel_power_W: float = None,
            use_market_maker_rate: bool = False):
        """
        Constructor of PVUserProfileStrategy
        :param power_profile: input profile for a day. Can be either a csv file path,
        or a dict with hourly data (Dict[int, float])
        or a dict with arbitrary time data (Dict[str, float])
        :param panel_count: number of solar panels for this PV plant
        :param final_selling_rate: lower threshold for the PV sale price
        """
        super().__init__(panel_count=panel_count,
                         initial_selling_rate=initial_selling_rate,
                         final_selling_rate=final_selling_rate,
                         fit_to_limit=fit_to_limit,
                         update_interval=update_interval,
                         energy_rate_decrease_per_update=energy_rate_decrease_per_update,
                         max_panel_power_W=max_panel_power_W,
                         use_market_maker_rate=use_market_maker_rate)
        self._power_profile_W = power_profile

    def _read_predefined_profile_for_pv(self) -> Dict[DateTime, float]:
        """
        Reads profile data from the power profile. Handles csv files and dicts.
        :return: key value pairs of time to energy in kWh
        """
        return read_arbitrary_profile(
            InputProfileTypes.POWER,
            self._power_profile_W)
