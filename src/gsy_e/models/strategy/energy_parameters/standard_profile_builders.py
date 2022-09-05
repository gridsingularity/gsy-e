import csv
from collections import defaultdict
from pathlib import Path

import pendulum

from gsy_e.gsy_e_core.util import d3a_path


class StandardProfile:
    """Class representing the Standard Solar Profile for forward products."""

    FILENAME = Path(d3a_path) / "resources/standard_solar_profile.csv"
    MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    FIELDNAMES = ["INTERVAL"] + MONTHS
    SLOT_LENGTH = pendulum.duration(minutes=15)
    SLOTS_IN_ONE_HOUR = pendulum.duration(hours=1) / SLOT_LENGTH

    def __init__(self):
        self._data: defaultdict = self._parse_profile_file()

    @classmethod
    def _parse_profile_file(cls) -> defaultdict:
        data = defaultdict(dict)
        with open(cls.FILENAME, "r", encoding="utf-8") as inf:
            reader = csv.DictReader(inf, fieldnames=cls.FIELDNAMES, delimiter=";")
            next(reader)  # Skip header line
            for row in reader:
                # Only keep time, discarding the date information to make the profile more general
                slot = pendulum.parse(row["INTERVAL"], exact=True)
                # The SSP is expressed in power (kW) units, so we convert it to energy (kWh)
                for month in cls.MONTHS:
                    data[month][slot] = float(row[month]) / cls.SLOTS_IN_ONE_HOUR

        return data
