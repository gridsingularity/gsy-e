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
import csv
import os
import ast
from enum import Enum
from pendulum import duration, from_format, from_timestamp, today, DateTime
from statistics import mean
from typing import Dict
from itertools import product
from d3a.constants import TIME_FORMAT, DATE_TIME_FORMAT, TIME_ZONE
from d3a.models.const import GlobalConfig

"""
Exposes mixins that can be used from strategy classes.
"""


class InputProfileTypes(Enum):
    IDENTITY = 1
    POWER = 2


def _str_to_datetime(time_str, time_format) -> DateTime:
    """
    Converts time_str into a pendulum (DateTime) object that either takes the global start date or
    the provided one, dependant on the time_format
    :return: DateTime
    """
    time = from_format(time_str, time_format, tz=TIME_ZONE)
    if time_format == DATE_TIME_FORMAT:
        return time
    elif time_format == TIME_FORMAT:
        return GlobalConfig.start_date.add(
            hours=time.hour, minutes=time.minute, seconds=time.second)
    else:
        raise ValueError("Provided time_format invalid.")


def default_profile_dict(val=None) -> Dict[DateTime, int]:
    """
    Expanding a dictionary that contains one key for every minute of the simulation time
    The keys are pendulum (DateTime) objects
    :return: Dict[DateTime, int]
    """
    if val is None:
        val = 0
    if GlobalConfig.sim_duration.days > 0:
        outdict = dict((GlobalConfig.start_date.add(days=day, hours=hour, minutes=minute), val)
                       for day, hour, minute in
                       product(range(GlobalConfig.sim_duration.days + 1), range(24), range(60)))
    else:
        outdict = dict((GlobalConfig.start_date.add(hours=hour, minutes=minute), val)
                       for hour, minute in product(range(24), range(60)))

    if GlobalConfig.market_count > 1:
        # this is for adding data points for the future markets
        added_market_count_minutes = int((GlobalConfig.market_count - 1) *
                                         GlobalConfig.slot_length.in_minutes())
        last_time = from_format(str(sorted(list(outdict.keys()))[-1]), DATE_TIME_FORMAT)

        for minute in range(1, added_market_count_minutes+1):
            outdict[last_time.add(minutes=minute)] = val

    return outdict


def _eval_time_format(time_dict: Dict) -> str:
    """
    Evaluates which time format the provided dictionary has, also checks if the time-format is
    consistent for each time_slot
    :return: TIME_FORMAT or DATE_TIME_FORMAT
    """
    try:
        [from_format(str(ti), TIME_FORMAT) for ti in time_dict.keys()]
        return TIME_FORMAT
    except ValueError:
        try:
            [from_format(str(ti), DATE_TIME_FORMAT) for ti in time_dict.keys()]
            return DATE_TIME_FORMAT
        except ValueError:
            raise Exception(f"Format of time-stamp is not one of ('{TIME_FORMAT}', "
                            f"'{DATE_TIME_FORMAT}')")


def _readCSV(path: str) -> Dict:
    """
    Read a 2-column csv profile file. First column is the time, second column
    is the value (power, energy, rate, ...)
    :param path: path to csv file
    :return: Dict[DateTime, value]
    """
    profile_data = {}
    with open(path) as csv_file:
        csv_rows = csv.reader(csv_file)
        for row in csv_rows:
            if len(row) == 0:
                raise Exception(f"There must not be an empty line in the profile file {path}")
            if len(row) != 2:
                row = row[0].split(";")
            try:
                profile_data[row[0]] = float(row[1])
            except ValueError:
                pass

    time_format = _eval_time_format(profile_data)
    return dict((_str_to_datetime(time_str, time_format), value)
                for time_str, value in profile_data.items())


def _calculate_energy_from_power_profile(profile_data_W: Dict[str, float],
                                         slot_length: duration) -> Dict[DateTime, float]:
    """
    Calculates energy from power profile. Does not use numpy, calculates avg power for each
    market slot and based on that calculates energy.
    :param profile_data_W: Power profile in W
    :param slot_length: slot length duration
    :return: a mapping from time to energy values in kWh
    """

    input_time_list = list(profile_data_W.keys())
    input_power_list_W = [float(dp) for dp in profile_data_W.values()]

    time0 = from_timestamp(0)
    input_time_seconds_list = [(ti - time0).in_seconds()
                               for ti in input_time_list]

    slot_time_list = [i for i in range(input_time_seconds_list[0], input_time_seconds_list[-1],
                                       slot_length.in_seconds())]

    second_power_list_W = [
        input_power_list_W[index - 1]
        for index, seconds in enumerate(input_time_seconds_list)
        for _ in range(seconds - input_time_seconds_list[index - 1])
    ]

    avg_power_kW = []
    for index, slot in enumerate(slot_time_list):
        first_index = index * slot_length.in_seconds()
        second_index = first_index + slot_length.in_seconds()
        if (first_index <= len(second_power_list_W)) or (second_index <= len(second_power_list_W)):
            avg_power_kW.append(mean(second_power_list_W[first_index:second_index]) / 1000.)

    slot_energy_kWh = list(map(lambda x: x / (duration(hours=1) / slot_length), avg_power_kW))

    return {from_timestamp(slot_time_list[ii]): energy
            for ii, energy in enumerate(slot_energy_kWh)
            }


def _fill_gaps_in_profile(input_profile: Dict=None) -> Dict:
    """
    Fills time steps, where no value is provided, with the value value of the
    last available time step.
    :param input_profile: Dict[Datetime: float, int, tuple]
    :return: continuous profile Dict[Datetime: float, int, tuple]
    """

    out_profile = default_profile_dict()

    if isinstance(list(input_profile.values())[0], tuple):
        current_val = (0, 0)
    else:
        current_val = 0

    for time in out_profile.keys():
        if time in input_profile.keys():
            current_val = input_profile[time]
        out_profile[time] = current_val

    return out_profile


def _read_from_different_sources_todict(input_profile) -> Dict[DateTime, float]:
    """
    Reads arbitrary profile.
    Handles csv, dict and string input.
    :param input_profile:Can be either a csv file path,
    or a dict with hourly data (Dict[int, float])
    or a dict with arbitrary time data (Dict[str, float])
    or a string containing a serialized dict of the aforementioned structure
    :return:
    """

    if os.path.isfile(str(input_profile)):
        # input is csv file
        profile = _readCSV(input_profile)
        _eval_time_period_consensus(profile)

    elif isinstance(input_profile, dict) or isinstance(input_profile, str):
        # input is profile

        if isinstance(input_profile, str):
            # input in JSON formatting
            profile = ast.literal_eval(input_profile)
            # Remove filename entry to support d3a-web profiles
            profile.pop("filename", None)
            time_format = _eval_time_format(profile)
            profile = {_str_to_datetime(key, time_format): val
                       for key, val in profile.items()}
        elif isinstance(list(input_profile.keys())[0], DateTime):
            return input_profile

        elif isinstance(list(input_profile.keys())[0], str):
            # input is dict with string keys that are properly formatted time stamps
            time_format = _eval_time_format(input_profile)
            profile = {_str_to_datetime(key, time_format): val
                       for key, val in input_profile.items()}

        elif isinstance(list(input_profile.keys())[0], int) or \
                isinstance(list(input_profile.keys())[0], float):
            # input is hourly profile

            profile = dict(
                (today(tz=TIME_ZONE).add(hours=hour), val)
                for hour, val in input_profile.items()
            )

        else:
            raise TypeError("Unsupported input type : " + str(list(input_profile.keys())[0]))

    elif isinstance(input_profile, int) or \
            isinstance(input_profile, float) or \
            isinstance(input_profile, tuple):
        # input is single value
        profile = default_profile_dict(val=input_profile)

    else:
        raise TypeError(f"Unsupported input type: {str(input_profile)}")

    return profile


def _eval_time_period_consensus(input_profile: Dict):
    """
    Checks whether the provided profile is providing information for the simulation time period
    :return:
    """
    input_time_list = list(input_profile.keys())
    simulation_time_list = [GlobalConfig.start_date,
                            GlobalConfig.start_date + GlobalConfig.sim_duration
                            - GlobalConfig.slot_length]
    if simulation_time_list[0] < input_time_list[0] or \
            simulation_time_list[-1] > input_time_list[-1]:
        raise ValueError(f"Provided profile is not overlapping with simulation time period "
                         f"(provided time period: {input_time_list[0].format(DATE_TIME_FORMAT)}, "
                         f"{input_time_list[-1].format(DATE_TIME_FORMAT)}, "
                         f"simulation time period: "
                         f"{simulation_time_list[0].format(DATE_TIME_FORMAT)}, "
                         f"{simulation_time_list[-1].format(DATE_TIME_FORMAT)})")


def read_arbitrary_profile(profile_type: InputProfileTypes,
                           input_profile) -> Dict[DateTime, float]:
    """
    Reads arbitrary profile.
    Handles csv, dict and string input.
    Fills gaps in the profile.
    :param profile_type: Can be either rate or power
    :param input_profile: Can be either a csv file path,
    or a dict with hourly data (Dict[int, float])
    or a dict with arbitrary time data (Dict[str, float])
    or a string containing a serialized dict of the aforementioned structure
    :return: a mapping from time to profile values
    """

    profile = _read_from_different_sources_todict(input_profile)

    if input_profile is not None:
        filled_profile = _fill_gaps_in_profile(profile)

        if profile_type == InputProfileTypes.POWER:
            return _calculate_energy_from_power_profile(filled_profile, GlobalConfig.slot_length)
        else:
            return filled_profile
