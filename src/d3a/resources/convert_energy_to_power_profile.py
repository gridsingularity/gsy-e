from d3a_interface.constants_limits import GlobalConfig
from d3a.models.read_user_profile import _readCSV, default_profile_dict
from pendulum import duration
import csv
import argparse
from itertools import product


def minute_profile_dict(val):
    if val is None:
        val = 0
    if GlobalConfig.sim_duration > duration(days=1):
        outdict = dict((GlobalConfig.start_date.add(days=day, hours=hour, minutes=minute), val)
                       for day, hour, minute in
                       product(range(GlobalConfig.sim_duration.days + 1), range(24), range(60)))
    else:
        outdict = dict((GlobalConfig.start_date.add(hours=hour, minutes=minute), val)
                       for hour, minute in product(range(24), range(60)))

    return outdict


def _fill_gaps_in_profile(input_profile):
    out_profile = minute_profile_dict(0)

    if isinstance(list(input_profile.values())[0], tuple):
        current_val = (0, 0)
    else:
        current_val = 0

    for time in out_profile.keys():
        if time in input_profile.keys():
            current_val = input_profile[time]
        out_profile[time] = current_val

    return out_profile


def convert_energy_to_power(e):
    return round(e * (duration(hours=1) / GlobalConfig.slot_length), 4)


def convert_energy_profile_to_power(input_profile, output_file):
    profile = _readCSV(input_profile)
    # Create a minute-resolution profile, filling the empty slots with previous values
    profile = _fill_gaps_in_profile(profile)
    GlobalConfig.sim_duration = duration(days=1) - duration(minutes=1)
    output_dict = default_profile_dict(0)
    for k, v in output_dict.items():
        # Average market slot values
        iter_duration = duration(minutes=0)
        averaged_value = 0
        while iter_duration < GlobalConfig.slot_length:
            averaged_value += profile[k + iter_duration]
            iter_duration += duration(minutes=1)
        averaged_value /= GlobalConfig.slot_length.minutes
        output_dict[k] = averaged_value

    power_profile = {k: convert_energy_to_power(float(v)) for k, v in output_dict.items()}
    with open(output_file, 'w') as csv_file:
        writer = csv.writer(csv_file)
        for key, value in power_profile.items():
            writer.writerow([key, value])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Convert an energy profile to power profile.')
    parser.add_argument('-i', '--input-file', help='input profile file', type=str, required=True)
    parser.add_argument('-o', '--output-file', help='output profile file', type=str, required=True)
    args = vars(parser.parse_args())
    convert_energy_profile_to_power(args["input_file"], args["output_file"])
