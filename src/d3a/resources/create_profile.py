#!/usr/bin/env python3

"""
To create a 5 day Profile, run:
./create_profile.py -i ./LOAD_DATA_1.csv -o ./LOAD_DATA_1_5d.csv -d 5
"""

from pendulum import from_format, DateTime
import csv
import argparse

from d3a.constants import TIME_FORMAT, DATE_TIME_FORMAT


def read_daily_profile_todict(daily_profile_fn):
    outdict = {}
    header = []
    firstline = True
    with open(daily_profile_fn, 'r') as csv_file:
        file_reader = csv.reader(csv_file, delimiter=';')
        for row in file_reader:
            if firstline:
                firstline = False
                header = [row[0], row[1]]
                continue
            outdict[from_format(row[0], TIME_FORMAT)] = float(row[1])

    return header, outdict


def write_profile_todict(profile_dict, header, outfile):
    with open(outfile, 'w') as csv_file:
        writer = csv.writer(csv_file, delimiter=';')
        writer.writerow(header)
        for time, value in profile_dict.items():
            writer.writerow([time.format(DATE_TIME_FORMAT), value])


def create_profile_from_daily_profile(n_days=365, year=2019, daily_profile_fn=None, out_fn=None):

    if daily_profile_fn is None:
        raise ValueError("No daily_profile_fn was provided")
    header, daily_profile_dict = read_daily_profile_todict(daily_profile_fn)
    profile_dict = {}
    for day in range(1, n_days):
        for time, value in daily_profile_dict.items():
            profile_dict[DateTime(year, 1, 1).add(
                days=day - 1, hours=time.hour, minutes=time.minute)] = value

    if out_fn is None:
        out_fn = daily_profile_fn.replace(".csv", "_year.csv")
    write_profile_todict(profile_dict, header, out_fn)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Creates a Load/Generation profile for a set'
                                                 'number of days from a daily profile')
    parser.add_argument('-y', '--year', help='year for timestamp', type=int, default=2019)
    parser.add_argument('-d', '--n-days', help='number of days', type=int, default=365)
    parser.add_argument('-i', '--input-file', help='daily profile file', type=str, required=True)
    parser.add_argument('-o', '--output-file', help='output profile file', type=str)
    args = vars(parser.parse_args())
    create_profile_from_daily_profile(n_days=args["n_days"], year=args["year"],
                                      daily_profile_fn=args["input_file"],
                                      out_fn=args["output_file"])
