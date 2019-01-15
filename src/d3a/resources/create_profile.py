#!/usr/bin/env python3

from datetime import datetime, timedelta
import csv
import argparse

ISO_TIME_FORMAT = "%Y-%m-%dT%H:%M:%S"


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
            outdict[datetime.strptime(row[0], "%H:%M")] = float(row[1])

    return header, outdict


def write_profile_todict(profile_dict, header, outfile):
    with open(outfile, 'w') as csv_file:
        writer = csv.writer(csv_file, delimiter=';')
        writer.writerow(header)
        for time, value in profile_dict.items():
            writer.writerow([time.strftime(ISO_TIME_FORMAT), value])


def create_profile_from_daily_profile(n_days=365, year=2019, daily_profile_fn="./LOAD_DATA_1.csv",
                                      out_fn=None):

    header, daily_profile_dict = read_daily_profile_todict(daily_profile_fn)
    profile_dict = {}
    for day in range(1, n_days):
        for time, value in daily_profile_dict.items():
            profile_dict[datetime(year, 1, 1) +
                         timedelta(day - 1, hours=time.hour, minutes=time.minute)] = value

    if out_fn is None:
        out_fn = daily_profile_fn.replace(".csv", "_year.csv")
    write_profile_todict(profile_dict, header, out_fn)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Creates a Load/Generation profile for a set'
                                                 'number of days from a daily profile ')

    parser.add_argument('-y', '--year', help='year for timestamp', type=int, default=2019)
    parser.add_argument('-d', '--n-days', help='number of days', type=int, default=365)
    parser.add_argument('-i', '--input-file', help='daily profile file', type=str, required=True)
    args = vars(parser.parse_args())
    create_profile_from_daily_profile()
