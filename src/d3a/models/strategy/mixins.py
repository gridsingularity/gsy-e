import csv
import os
import numpy as np
from datetime import datetime
from pendulum import Interval
from statistics import mean


class ReadProfileMixin:

    @staticmethod
    def _readCSV(path):
        profile_data = {}
        with open(path) as csvfile:
            next(csvfile)
            csv_rows = csv.reader(csvfile, delimiter=';')
            for row in csv_rows:
                timestr, wattstr = row
                profile_data[timestr] = float(wattstr)
        return profile_data

    @staticmethod
    def _interpolate_profile_data_for_market_slot(profile_data, time_format, slot_length):
        """
        Interpolates power curves onto slot times and converts it into energy (kWh)

        The intrinsic conversion to seconds is done in order to enable slot-lengths < 1 minute
        """

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

    @staticmethod
    def _calculate_energy_from_power_profile(profile_data, time_format, slot_length):
        """
        Calculates energy from power profile. Does not use numpy, calculates avg power for each
        market slot and based on that calculates energy.
        """

        timestr_solar_array = list(profile_data.keys())
        solar_power_input_W = list(profile_data.values())
        time0 = datetime.utcfromtimestamp(0)
        time_solar_array = [
            (datetime.strptime(ti, time_format) - time0).seconds
            for ti in timestr_solar_array
        ]
        whole_day_sec = 24 * 60 * 60
        time_solar_array.append(whole_day_sec)
        solar_power_array_W = [
            solar_power_input_W[index - 1]
            for index, seconds in enumerate(time_solar_array)
            for _ in range(seconds - time_solar_array[index - 1])
        ]
        slot_time_list = np.arange(0, whole_day_sec, slot_length.seconds)
        avg_power_kW = [
            mean(solar_power_array_W[
                    index * slot_length.seconds:index * slot_length.seconds + slot_length.seconds
                 ]) / 1000.0
            for index, slot in enumerate(slot_time_list)
        ]
        slot_energy_kWh = list(map(lambda x: x / (Interval(hours=1) / slot_length), avg_power_kW))

        return {datetime.utcfromtimestamp(slot_time_list[ii]).strftime(time_format):
                slot_energy_kWh[ii]
                for ii in range(len(slot_energy_kWh))
                }

    def read_power_profile_csv_to_energy(self, profile_path, time_format, slot_length):
        profile_data = self._readCSV(profile_path)
        return self._interpolate_profile_data_for_market_slot(
            profile_data, time_format, slot_length
        )

    def read_arbitrary_power_profile_W_to_energy_kWh(self, daily_load_profile, slot_length):
        if os.path.isfile(str(daily_load_profile)):
            return self.read_power_profile_csv_to_energy(
                daily_load_profile,
                "%H:%M",
                slot_length
            )
        elif isinstance(daily_load_profile, dict):
            if isinstance(list(daily_load_profile.keys())[0], str):
                # Assume that the time fields are properly formatted.
                return self._calculate_energy_from_power_profile(
                    daily_load_profile,
                    "%H:%M",
                    slot_length
                )
            elif isinstance(list(daily_load_profile.keys())[0], int):
                # If it is an integer assume an hourly profile
                input_profile = {hour: 0 for hour in range(24)}
                input_profile.update(daily_load_profile)
                input_profile = dict(
                    (f"{k:02}:{m:02}", v)
                    for k, v in input_profile.items()
                    for m in range(60)
                )
                return self._calculate_energy_from_power_profile(
                    input_profile,
                    "%H:%M",
                    slot_length
                )
            else:
                raise TypeError("Unsupported type for load strategy input timestamp field: " +
                                str(daily_load_profile.keys()[0]))
        else:
            raise TypeError(f"Unsupported type for load strategy input: {str(daily_load_profile)}")
