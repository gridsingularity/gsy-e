import csv
from typing import Dict  # noqa

from pendulum import Time, Interval  # noqa

from d3a.models.strategy.pv import PVStrategy
from d3a.models.strategy.const import DEFAULT_RISK, MIN_PV_SELLING_PRICE, DEFAULT_CLOUD
import pathlib


class PVPredefinedStrategy(PVStrategy):

    def __init__(self, risk=DEFAULT_RISK,
                 min_selling_price=MIN_PV_SELLING_PRICE, cloud=DEFAULT_CLOUD):
        super().__init__(panel_count=1, risk=risk, min_selling_price=min_selling_price)
        self.data = {}
        if cloud == 0:  # 0:sunny
            self.readCSV(pathlib.Path(pathlib.Path.cwd(),
                                      'src/d3a/resources/PV_DATA_sunny.csv').expanduser())
        elif cloud == 2:  # 2:partial
            self.readCSV(pathlib.Path(pathlib.Path.cwd(),
                                      'src/d3a/resources/PV_DATA_partial.csv').expanduser())
        elif cloud == 1:  # 1:cloudy
            self.readCSV(pathlib.Path(pathlib.Path.cwd(),
                                      'src/d3a/resources/PV_DATA_cloudy.csv').expanduser())

    def readCSV(self, path):
        with open(path) as csvfile:
            next(csvfile)
            csv_rows = csv.reader(csvfile, delimiter=';')
            for row in csv_rows:
                k, v = row
                self.data[k] = float(v)

    def produced_energy_forecast_real_data(self):
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
            self.energy_production_forecast_kWh[slot_time] = self.data[slot_time.format('%H:%M')]
