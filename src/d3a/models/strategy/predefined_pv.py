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
from pendulum import duration

from d3a.d3a_core.util import find_object_of_same_weekday_and_time, d3a_path
from d3a.models.strategy.pv import PVStrategy
from d3a_interface.constants_limits import ConstSettings
from d3a.models.read_user_profile import read_arbitrary_profile, InputProfileTypes
from d3a_interface.utils import key_in_dict_and_not_none

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
                  'use_market_maker_rate')

    def __init__(
            self, panel_count: int = 1,
            initial_selling_rate: float = ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE,
            final_selling_rate: float = ConstSettings.PVSettings.SELLING_RATE_RANGE.final,
            cloud_coverage: int = None,
            fit_to_limit: bool = True,
            update_interval=None,
            energy_rate_decrease_per_update=None,
            use_market_maker_rate: bool = False):
        """
        Constructor of PVPredefinedStrategy
        :param panel_count: Number of solar panels for this PV plant
        :param initial_selling_rate: Upper Threshold for PV offers
        :param final_selling_rate: Lower Threshold for PV offers
        :param cloud_coverage: cloud conditions.
                                0=sunny,
                                1=partially cloudy,
                                2=cloudy,
                                4=use global profile
                                None=use global cloud_coverage (default)
        :param fit_to_limit: Linear curve following initial_selling_rate & final_selling_rate
        :param update_interval: Interval after which PV will update its offer
        :param energy_rate_decrease_per_update: Slope of PV Offer change per update
        """

        if update_interval is None:
            update_interval = \
                duration(minutes=ConstSettings.GeneralSettings.DEFAULT_UPDATE_INTERVAL)

        super().__init__(panel_count=panel_count,
                         initial_selling_rate=initial_selling_rate,
                         final_selling_rate=final_selling_rate,
                         fit_to_limit=fit_to_limit,
                         update_interval=update_interval,
                         energy_rate_decrease_per_update=energy_rate_decrease_per_update,
                         max_panel_power_W=None,
                         use_market_maker_rate=use_market_maker_rate
                         )
        self.cloud_coverage = cloud_coverage
        self._power_profile_index = cloud_coverage
        self.power_profile = {}

    def read_config_event(self):
        # this is to trigger to read from self.area.config.cloud_coverage:
        self.cloud_coverage = None
        self.set_produced_energy_forecast_kWh_future_markets(reconfigure=True)

    def set_produced_energy_forecast_kWh_future_markets(self, reconfigure=True):
        self._power_profile_index = self.cloud_coverage \
            if self.cloud_coverage is not None else self.area.config.cloud_coverage
        if reconfigure:
            self._read_predefined_profile_for_pv()
        for market in self.area.all_markets:
            slot_time = market.time_slot
            if slot_time not in self.energy_production_forecast_kWh or reconfigure:
                self.energy_production_forecast_kWh[slot_time] = \
                    find_object_of_same_weekday_and_time(self.power_profile, slot_time) \
                    * self.panel_count
                self.state.available_energy_kWh[slot_time] = \
                    self.energy_production_forecast_kWh[slot_time]

    def _read_predefined_profile_for_pv(self):
        """
        Reads profile data from the predefined power profiles. Reads config and constructor
        parameters and selects the appropriate predefined profile.
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
            raise ValueError("Energy_profile has to be in [0,1,2,4]")

        # Populate energy production forecast data
        self.power_profile = read_arbitrary_profile(
            InputProfileTypes.POWER, str(profile_path))

    def area_reconfigure_event(self, **kwargs):
        if key_in_dict_and_not_none(kwargs, 'cloud_coverage'):
            self.cloud_coverage = kwargs['cloud_coverage']
        super().area_reconfigure_event(**kwargs)


class PVUserProfileStrategy(PVPredefinedStrategy):
    """
        Strategy responsible for reading a profile in the form of a dict of values.
    """
    parameters = ('power_profile', 'panel_count', 'initial_selling_rate', 'final_selling_rate',
                  'fit_to_limit', 'update_interval', 'energy_rate_decrease_per_update',
                  'use_market_maker_rate')

    def __init__(
            self, power_profile, panel_count: int = 1,
            initial_selling_rate: float = ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE,
            final_selling_rate: float = ConstSettings.PVSettings.SELLING_RATE_RANGE.final,
            fit_to_limit: bool = True,
            update_interval=duration(
                minutes=ConstSettings.GeneralSettings.DEFAULT_UPDATE_INTERVAL),
            energy_rate_decrease_per_update=None,
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
                         use_market_maker_rate=use_market_maker_rate)
        self._power_profile_W = power_profile

    def _read_predefined_profile_for_pv(self):
        """
        Reads profile data from the power profile. Handles csv files and dicts.
        :return: key value pairs of time to energy in kWh
        """
        self.power_profile = read_arbitrary_profile(
            InputProfileTypes.POWER,
            self._power_profile_W)

    def area_reconfigure_event(self, **kwargs):
        super().area_reconfigure_event(**kwargs)
        if key_in_dict_and_not_none(kwargs, 'power_profile'):
            self._power_profile_W = kwargs['power_profile']
        self.set_produced_energy_forecast_kWh_future_markets(reconfigure=True)
