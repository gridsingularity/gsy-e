"""
Creates a PV that uses a profile as input for its power values, either predefined or provided
by the user.
"""
import pathlib

from d3a import TIME_FORMAT, PENDULUM_TIME_FORMAT
from d3a.util import generate_market_slot_list
from d3a.models.strategy.pv import PVStrategy
from d3a.models.strategy.const import ConstSettings
from d3a.models.strategy.read_user_profile import read_profile_csv_to_dict, read_arbitrary_profile
from d3a.models.strategy.read_user_profile import InputProfileTypes
from d3a.util import d3a_path
from typing import Dict


class PVPredefinedStrategy(PVStrategy):
    """
        Strategy responsible for using one of the predefined PV profiles.
    """
    parameters = ('panel_count', 'risk')

    def __init__(self, risk: int=ConstSettings.GeneralSettings.DEFAULT_RISK, panel_count: int=1,
                 min_selling_rate: float=ConstSettings.PVSettings.MIN_SELLING_RATE,
                 cloud_coverage: int=None,
                 initial_rate_option: int=ConstSettings.PVSettings.INITIAL_RATE_OPTION,
                 energy_rate_decrease_option=ConstSettings.PVSettings.RATE_DECREASE_OPTION,
                 energy_rate_decrease_per_update=ConstSettings.GeneralSettings.
                 ENERGY_RATE_DECREASE_PER_UPDATE):
        """
        Constructor of PVPredefinedStrategy
        :param risk: PV risk parameter
        :param panel_count: number of solar panels for this PV plant
        :param min_selling_rate: lower threshold for the PV sale price
        :param cloud_coverage: cloud conditions. 0=sunny, 1=partially cloudy, 2=cloudy
        """
        super().__init__(panel_count=panel_count, risk=risk,
                         min_selling_rate=min_selling_rate,
                         initial_rate_option=initial_rate_option,
                         energy_rate_decrease_option=energy_rate_decrease_option,
                         energy_rate_decrease_per_update=energy_rate_decrease_per_update
                         )
        self._power_profile_index = cloud_coverage
        self._time_format = TIME_FORMAT

    def event_activate(self):
        """
        Runs on activate event. Reads the power profile data and calculates the required energy
        for each slot.
        :return: None
        """
        # TODO: Need to have 2-stage initialization as well, because the area objects are not
        # created when the constructor is executed if we inherit from a mixin class,
        # therefore config cannot be read at that point
        data = self._read_predefined_profile_for_pv()

        for slot_time in generate_market_slot_list(self.area):
            self.energy_production_forecast_kWh[slot_time] = \
                data[slot_time.format(PENDULUM_TIME_FORMAT)] * self.panel_count
            self.state.available_energy_kWh[slot_time] = \
                self.energy_production_forecast_kWh[slot_time]

        # TODO: A bit clumsy, but this decrease price calculation needs to be added here as well
        # Need to refactor once we convert the config object to a singleton that is shared globally
        # in the simulation
        self._decrease_price_every_nr_s = \
            (self.area.config.tick_length.seconds *
             ConstSettings.GeneralSettings.MAX_OFFER_TRAVERSAL_LENGTH + 1)

    def _read_predefined_profile_for_pv(self) -> Dict[str, float]:
        """
        Reads profile data from the predefined power profiles. Reads config and constructor
        parameters and selects the appropriate rpedefined profile.
        :return: key value pairs of time to energy in kWh
        """
        if self._power_profile_index is None:
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
        return read_profile_csv_to_dict(
            InputProfileTypes.POWER, str(profile_path),
            self.area.config.slot_length)


class PVUserProfileStrategy(PVPredefinedStrategy):
    """
        Strategy responsible for reading a profile in the form of a dict of values.
    """
    parameters = ('power_profile', 'risk', 'panel_count')

    def __init__(self, power_profile, risk: int=ConstSettings.GeneralSettings.DEFAULT_RISK,
                 panel_count: int=1,
                 min_selling_rate: float=ConstSettings.PVSettings.MIN_SELLING_RATE,
                 initial_rate_option: int=ConstSettings.PVSettings.INITIAL_RATE_OPTION,
                 energy_rate_decrease_option=ConstSettings.PVSettings.RATE_DECREASE_OPTION,
                 energy_rate_decrease_per_update=ConstSettings.GeneralSettings.
                 ENERGY_RATE_DECREASE_PER_UPDATE
                 ):
        """
        Constructor of PVUserProfileStrategy
        :param power_profile: input profile for a day. Can be either a csv file path,
        or a dict with hourly data (Dict[int, float])
        or a dict with arbitrary time data (Dict[str, float])
        :param risk: PV risk parameter
        :param panel_count: number of solar panels for this PV plant
        :param min_selling_rate: lower threshold for the PV sale price
        """
        super().__init__(risk=risk, panel_count=panel_count,
                         min_selling_rate=min_selling_rate,
                         initial_rate_option=initial_rate_option,
                         energy_rate_decrease_option=energy_rate_decrease_option,
                         energy_rate_decrease_per_update=energy_rate_decrease_per_update
                         )
        self._power_profile_W = power_profile
        self._time_format = TIME_FORMAT

    def _read_predefined_profile_for_pv(self) -> Dict[str, float]:
        """
        Reads profile data from the power profile. Handles csv files and dicts.
        :return: key value pairs of time to energy in kWh
        """
        return read_arbitrary_profile(
            InputProfileTypes.POWER,
            self._power_profile_W,
            slot_length=self.area.config.slot_length)
