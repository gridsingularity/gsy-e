import csv
import pathlib
import numpy as np
from datetime import datetime
import d3a

from d3a.models.strategy.pv import PVStrategy
from d3a.models.strategy.const import DEFAULT_RISK, MIN_PV_SELLING_PRICE, DEFAULT_PV_ENERGY_PROFILE

from typing import Dict  # noqa
from pendulum import Time  # noqa

d3a_path = d3a.__path__[0]


class PVPredefinedStrategy(PVStrategy):
    parameters = ('min_selling_price', 'energy_profile')

    def __init__(self, risk=DEFAULT_RISK,
                 min_selling_price=MIN_PV_SELLING_PRICE, energy_profile=DEFAULT_PV_ENERGY_PROFILE):
        super().__init__(panel_count=1, risk=risk, min_selling_price=min_selling_price)

        self.data = {}
        self.solar_data = {}
        self.time_format = "%H:%M"
        self.interp_energy_kWh = np.array(())
        if energy_profile == 0:  # 0:sunny
            self.readCSV(pathlib.Path(d3a_path + '/resources/Solar_Curve_W_sunny.csv'))
        elif energy_profile == 2:  # 2:partial
            self.readCSV(pathlib.Path(d3a_path + '/resources/Solar_Curve_W_partial.csv'))
        elif energy_profile == 1:  # 1:cloudy
            self.readCSV(pathlib.Path(d3a_path + '/resources/Solar_Curve_W_cloudy.csv'))
        else:
            raise ValueError("Energy_profile has to be in [0,1,2]")

    def readCSV(self, path):
        with open(path) as csvfile:
            next(csvfile)
            csv_rows = csv.reader(csvfile, delimiter=';')
            for row in csv_rows:
                timestr, wattstr = row
                self.solar_data[timestr] = float(wattstr)

    def prepare_solar_data(self):
        """
        Interpolates solar power curves onto slot times and converts it into energy (kWh)

        The intrinsic conversion to seconds is done in order to enable slot-lengths < 1 minute
        """

        timestr_solar_array = np.array(list(self.solar_data.keys()))
        solar_power_W = np.array(list(self.solar_data.values()))

        time0 = datetime.utcfromtimestamp(0)
        time_solar_array = np.array([
            (datetime.strptime(ti, self.time_format) - time0).seconds
            for ti in timestr_solar_array
                                    ])

        whole_day_sec = 24 * 60 * 60
        tt = np.append(time_solar_array, whole_day_sec)
        timediff_array = [j - i for i, j in zip(tt[:-1], tt[1:])]
        solar_energy_kWh = solar_power_W * timediff_array / 60 / 60 / 1000.

        slot_time_list = np.arange(0, whole_day_sec, self.area.config.slot_length.seconds)

        self.interp_energy_kWh = np.interp(slot_time_list, time_solar_array, solar_energy_kWh)

        return {datetime.utcfromtimestamp(slot_time_list[ii]).strftime(self.time_format):
                self.interp_energy_kWh[ii]
                for ii in range(len(self.interp_energy_kWh))
                }

    def produced_energy_forecast_real_data(self):

        self.data = self.prepare_solar_data()

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
                self.data[slot_time.format(self.time_format)]
