"""
Exposes mixins that can be used from strategy classes.
"""
import csv
import os
import ast
from enum import Enum
from datetime import datetime
from pendulum import duration
from statistics import mean
from typing import Dict
from itertools import product
from d3a import TIME_FORMAT


class InputProfileTypes(Enum):
    RATE = 1
    POWER = 2


def default_profile_dict():
    return dict((datetime(year=2000, month=1, day=1, hour=hour, minute=minute).
                 strftime(TIME_FORMAT), 0) for hour, minute in product(range(24), range(60)))


class ReadProfileMixin:
    """
    Introduces read profile functionality for a strategy class.
    """
    @staticmethod
    def _readCSV(path: str) -> Dict[str, float]:
        """
        Read a 2-column csv profile file. First column is the time, second column
        is the value (power, energy ...)
        :param path: path of the csv file
        :return: key-value pairs of the time and values
        """
        profile_data = {}
        with open(path) as csvfile:
            next(csvfile)
            csv_rows = csv.reader(csvfile, delimiter=';')
            for row in csv_rows:
                timestr, wattstr = row
                profile_data[timestr] = float(wattstr)
        return profile_data

    @staticmethod
    def _calculate_energy_from_power_profile(profile_data_W: Dict[str, float],
                                             slot_length: duration) -> Dict[str, float]:
        """
        Calculates energy from power profile. Does not use numpy, calculates avg power for each
        market slot and based on that calculates energy.
        :param profile_data_W: Power profile in W, in the same format as the result of _readCSV
        :param slot_length: slot length duration
        :return: a mapping from time to energy values in kWh
        """

        timestr_solar_array = list(profile_data_W.keys())
        solar_power_input_W = list(profile_data_W.values())
        time0 = datetime.utcfromtimestamp(0)
        time_solar_array = [
            (datetime.strptime(ti, TIME_FORMAT) - time0).seconds
            for ti in timestr_solar_array
        ]
        whole_day_sec = 24 * 60 * 60
        time_solar_array.append(whole_day_sec)
        solar_power_array_W = [
            solar_power_input_W[index - 1]
            for index, seconds in enumerate(time_solar_array)
            for _ in range(seconds - time_solar_array[index - 1])
        ]
        slot_time_list = [i for i in range(0, whole_day_sec, slot_length.seconds)]
        avg_power_kW = [
            mean(solar_power_array_W[
                    index * slot_length.seconds:index * slot_length.seconds + slot_length.seconds
                 ]) / 1000.0
            for index, slot in enumerate(slot_time_list)
        ]
        slot_energy_kWh = list(map(lambda x: x / (duration(hours=1) / slot_length), avg_power_kW))

        return {datetime.utcfromtimestamp(slot_time_list[ii]).strftime(TIME_FORMAT):
                slot_energy_kWh[ii]
                for ii in range(len(slot_energy_kWh))
                }

    @classmethod
    def read_profile_csv_to_dict(cls, profile_type: InputProfileTypes,
                                 profile_path: str,
                                 slot_length: duration) -> Dict[str, float]:
        """
        Reads power profile from csv and converts it to energy
        :param profile_path: path of the csv file
        :param slot_length: slot length duration
        :return: a mapping from time to energy values in kWh
        """
        profile_data = cls._readCSV(profile_path)
        if profile_type == InputProfileTypes.RATE:
            return cls._fill_gaps_in_rate_profile(profile_data)
        elif profile_type == InputProfileTypes.POWER:
            return cls._calculate_energy_from_power_profile(
                profile_data, slot_length
            )

    @staticmethod
    def _fill_gaps_in_rate_profile(rate_profile_input: Dict) -> Dict:
        """
        Fills time steps, where no rate is provided, with the rate value of the
        last available time step.
        :param rate_profile_input: dict(str: float)
        :return: continuous rate profile (dict)
        """

        rate_profile = default_profile_dict()
        current_rate = 0
        for hour, minute in product(range(24), range(60)):
            time_str = datetime(year=2000, month=1, day=1, hour=hour, minute=minute).\
                strftime(TIME_FORMAT)

            if time_str in rate_profile_input.keys():
                current_rate = rate_profile_input[time_str]
            rate_profile[time_str] = current_rate

        return rate_profile

    @classmethod
    def read_arbitrary_profile(cls, profile_type: InputProfileTypes,
                               daily_profile,
                               slot_length=duration()) -> Dict[str, float]:
        """
        Reads arbitrary profile.
        Handles csv, dict and string input.
        :param profile_type: Can be either rate or power
        :param daily_profile: Can be either a csv file path,
        or a dict with hourly data (Dict[int, float])
        or a dict with arbitrary time data (Dict[str, float])
        or a string containing a serialized dict of the aforementioned structure
        :param slot_length: slot length duration
        :return: a mapping from time to energy values in kWh
        """

        if os.path.isfile(str(daily_profile)):
            return cls.read_profile_csv_to_dict(
                profile_type,
                daily_profile,
                slot_length
            )
        elif isinstance(daily_profile, dict) or isinstance(daily_profile, str):

            if isinstance(daily_profile, str):
                # JSON
                input_profile = ast.literal_eval(daily_profile)
                input_profile = {k: float(v) for k, v in input_profile.items()}

            elif isinstance(list(daily_profile.keys())[0], str):
                # Assume that the time fields are properly formatted.
                input_profile = daily_profile

            elif isinstance(list(daily_profile.keys())[0], int) or \
                    isinstance(list(daily_profile.keys())[0], float):
                # If it is an integer assume an hourly profile
                input_profile = dict(
                    (datetime(year=2000, month=1, day=1, hour=hour).
                     strftime(TIME_FORMAT), val)
                    for hour, val in daily_profile.items()
                )

            else:
                raise TypeError("Unsupported input type : " + str(list(daily_profile.keys())[0]))

        elif isinstance(daily_profile, int) or \
                isinstance(daily_profile, float) or \
                isinstance(daily_profile, tuple):
            input_profile = default_profile_dict()
            for key in input_profile.keys():
                input_profile[key] = daily_profile

        else:
            raise TypeError(f"Unsupported input type: {str(daily_profile)}")

        if input_profile is not None:
            filled_profile = cls._fill_gaps_in_rate_profile(input_profile)
            if profile_type == InputProfileTypes.POWER:
                return cls._calculate_energy_from_power_profile(
                    filled_profile,
                    slot_length)
            else:
                return filled_profile
