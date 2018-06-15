import csv
import numpy as np
from datetime import datetime


class ReadProfileMixin:

    def _readCSV(self, path):
        profile_data = {}
        with open(path) as csvfile:
            next(csvfile)
            csv_rows = csv.reader(csvfile, delimiter=';')
            for row in csv_rows:
                timestr, wattstr = row
                profile_data[timestr] = float(wattstr)
        return profile_data

    def read_power_profile_to_energy(self, profile_path, time_format, slot_length):
        """
        Interpolates power curves onto slot times and converts it into energy (kWh)

        The intrinsic conversion to seconds is done in order to enable slot-lengths < 1 minute
        """

        profile_data = self._readCSV(profile_path)

        timestr_solar_array = np.array(list(profile_data.keys()))
        solar_power_W = np.array(list(profile_data.values()))

        time0 = datetime.utcfromtimestamp(0)
        time_solar_array = np.array([
            (datetime.strptime(ti, time_format) - time0).seconds
            for ti in timestr_solar_array
                                    ])

        whole_day_sec = 24 * 60 * 60
        tt = np.append(time_solar_array, whole_day_sec)
        timediff_array = [j - i for i, j in zip(tt[:-1], tt[1:])]
        solar_energy_kWh = solar_power_W * timediff_array / 60 / 60 / 1000.

        slot_time_list = np.arange(0, whole_day_sec, slot_length.seconds)

        interp_energy_kWh = np.interp(slot_time_list, time_solar_array, solar_energy_kWh)

        return {datetime.utcfromtimestamp(slot_time_list[ii]).strftime(time_format):
                interp_energy_kWh[ii]
                for ii in range(len(interp_energy_kWh))
                }
