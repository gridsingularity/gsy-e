import csv
import pathlib

from d3a.models.strategy.pv import PVStrategy
from d3a.models.strategy.const import DEFAULT_RISK, MIN_PV_SELLING_PRICE


class PVPredefinedStrategy(PVStrategy):
    parameters = ('panel_count', 'risk')

    def __init__(self, risk=DEFAULT_RISK, panel_count=1,
                 min_selling_price=MIN_PV_SELLING_PRICE):
        super().__init__(panel_count=panel_count, risk=risk, min_selling_price=min_selling_price)
        self.data = {}
        if self.owner.config.cloud_coverage == 0:  # 0:sunny
            profile_filename = 'src/d3a/resources/PV_DATA_sunny.csv'
        elif self.owner.config.cloud_coverage == 1:  # 1:cloudy
            profile_filename = 'src/d3a/resources/PV_DATA_cloudy.csv'
        elif self.owner.config.cloud_coverage == 2:  # 2:partial
            profile_filename = 'src/d3a/resources/PV_DATA_partial.csv'
        else:
            raise ValueError("Cloud coverage setting should be between 0 and 2.")
        self._readCSV(pathlib.Path(pathlib.Path.cwd(), profile_filename).expanduser())

    def _readCSV(self, path):
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
