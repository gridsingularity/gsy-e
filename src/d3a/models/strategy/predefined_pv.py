"""
Creates a PV that uses a profile as input for its power values, either predefined or provided
by the user.
"""
import pathlib
import d3a
import inspect
import os
from d3a.models.strategy import ureg
from d3a.models.strategy.pv import PVStrategy
from d3a.models.strategy.const import ConstSettings
from d3a.models.strategy.mixins import ReadProfileMixin
from typing import Dict


d3a_path = os.path.dirname(inspect.getsourcefile(d3a))


class PVPredefinedStrategy(ReadProfileMixin, PVStrategy):
    """
        Strategy responsible for using one of the predefined PV profiles.
    """
    parameters = ('panel_count', 'risk')

    def __init__(self, risk: int=ConstSettings.DEFAULT_RISK, panel_count: int=1,
                 min_selling_price: float=ConstSettings.MIN_PV_SELLING_PRICE,
                 cloud_coverage: int=None,
                 initial_pv_rate_option: int=ConstSettings.INITIAL_PV_RATE_OPTION):
        """
        Constructor of PVPredefinedStrategy
        :param risk: PV risk parameter
        :param panel_count: number of solar panels for this PV plant
        :param min_selling_price: lower threshold for the PV sale price
        :param cloud_coverage: cloud conditions. 0=sunny, 1=partially cloudy, 2=cloudy
        """
        super().__init__(panel_count=panel_count, risk=risk,
                         min_selling_price=min_selling_price,
                         initial_pv_rate_option=initial_pv_rate_option)
        self._power_profile_index = cloud_coverage
        self._time_format = "%H:%M"

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

        for slot_time in [
            self.area.now + (self.area.config.slot_length * i)
            for i in range(
                (
                        self.area.config.duration
                        + (
                                self.area.config.market_count *
                                self.area.config.slot_length)
                ) // self.area.config.slot_length)
        ]:
            self.energy_production_forecast_kWh[slot_time] = \
                data[slot_time.format(self._time_format)]

        # TODO: A bit clumsy, but this decrease price calculation needs to be added here as well
        # Need to refactor once we convert the config object to a singleton that is shared globally
        # in the simulation
        self._decrease_price_every_nr_s = \
            (self.area.config.tick_length.seconds * ConstSettings.MAX_OFFER_TRAVERSAL_LENGTH + 1) \
            * ureg.seconds

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
        return self.read_power_profile_csv_to_energy(str(profile_path),
                                                     self._time_format,
                                                     self.area.config.slot_length)


class PVUserProfileStrategy(PVPredefinedStrategy):
    """
        Strategy responsible for reading a profile in the form of a dict of values.
    """
    parameters = ('power_profile', 'risk', 'panel_count')

    def __init__(self, power_profile, risk: int=ConstSettings.DEFAULT_RISK, panel_count: int=1,
                 min_selling_price: float=ConstSettings.MIN_PV_SELLING_PRICE,
                 initial_pv_rate_option: int=ConstSettings.INITIAL_PV_RATE_OPTION):
        """
        Constructor of PVUserProfileStrategy
        :param power_profile: input profile for a day. Can be either a csv file path,
        or a dict with hourly data (Dict[int, float])
        or a dict with arbitrary time data (Dict[str, float])
        :param risk: PV risk parameter
        :param panel_count: number of solar panels for this PV plant
        :param min_selling_price: lower threshold for the PV sale price
        """
        super().__init__(risk=risk, panel_count=panel_count,
                         min_selling_price=min_selling_price,
                         initial_pv_rate_option=initial_pv_rate_option)
        self._power_profile_W = power_profile
        self._time_format = "%H:%M"

    def _read_predefined_profile_for_pv(self) -> Dict[str, float]:
        """
        Reads profile data from the power profile. Handles csv files and dicts.
        :return: key value pairs of time to energy in kWh
        """
        return self.read_arbitrary_power_profile_W_to_energy_kWh(
            self._power_profile_W, self.area.config.slot_length
        )
