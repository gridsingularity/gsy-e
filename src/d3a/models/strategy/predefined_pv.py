import csv
from typing import Dict  # noqa

from pendulum import Time, Interval  # noqa

from d3a.models.strategy.pv import PVStrategy
from d3a.models.strategy.const import DEFAULT_RISK, MIN_PV_SELLING_PRICE


class PVPredefinedStrategy(PVStrategy):

    def __init__(self, path, risk=DEFAULT_RISK, min_selling_price=MIN_PV_SELLING_PRICE):
        super().__init__(risk, min_selling_price)
        self.readCSV(path)

    def readCSV(self, path):
        with open(path) as csvfile:
            next(csvfile)
            readCSV = csv.reader(csvfile, delimiter=';')
            # self.rows = [r for r in readCSV]
            # print(self.rows)
            for row in readCSV:
                k, v = row
                self.data[k] = float(v)
            # print("CSV Data: {}".format(self.data))
