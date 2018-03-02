import csv
import json
import logging
import pathlib

from d3a.models.market import Trade
from d3a.models.strategy.fridge import FridgeStrategy
from d3a.models.strategy.greedy_night_storage import NightStorageStrategy
from d3a.models.strategy.load_hours_fb import LoadHoursStrategy
from d3a.models.strategy.pv import PVStrategy
from d3a.models.strategy.storage import StorageStrategy

_log = logging.getLogger(__name__)


def export(root_area, path, subdir):
    """Export all data of the finished simulation in one CSV file per area."""
    try:
        directory = pathlib.Path(path or "~/d3a-simulation", subdir).expanduser()
        directory.mkdir(exist_ok=True, parents=True)
    except Exception as ex:
        _log.error("Could not open directory for csv exports: %s" % str(ex))
        return
    _export_area_with_children(root_area, directory)
    _export_overview(root_area, directory)


def _export_area_with_children(area, directory):
    if area.children:
        subdirectory = pathlib.Path(directory, area.slug.replace(' ', '_'))
        subdirectory.mkdir(exist_ok=True, parents=True)
        for child in area.children:
            _export_area_with_children(child, subdirectory)
    _export_area_flat(area, directory)
    if area.children:
        _export_area_energy(area, directory)


def _file_path(directory, slug):
    file_name = ("%s.csv" % slug).replace(' ', '_')
    return directory.joinpath(file_name).as_posix()


class ExportData:
    def __init__(self, area):
        self.area = area

    @staticmethod
    def create(area):
        return ExportUpperLevelData(area) if area.children else ExportLeafData(area)


class ExportUpperLevelData(ExportData):
    def __init__(self, area):
        super(ExportUpperLevelData, self).__init__(area)

    def labels(self):
        return ['slot',
                'avg trade price [EUR]',
                'min trade price [EUR]',
                'max trade price [EUR]',
                '# trades',
                'total energy traded [kWh]',
                'total trade volume [EUR]']

    def rows(self):
        markets = self.area.past_markets
        return [self._row(slot, markets[slot]) for slot in markets]

    def _row(self, slot, market):
        return [slot,
                market.avg_trade_price,
                market.min_trade_price,
                market.max_trade_price,
                len(market.trades),
                sum(trade.offer.energy for trade in market.trades),
                sum(trade.offer.price for trade in market.trades)]


class ExportLeafData(ExportData):
    def __init__(self, area):
        super(ExportLeafData, self).__init__(area)

    def labels(self):
        return ['slot', 'energy balance [kWh]'] + self._specific_labels()

    def _specific_labels(self):
        if isinstance(self.area.strategy, FridgeStrategy):
            return ['temperature [°C]']
        elif isinstance(self.area.strategy, (StorageStrategy, NightStorageStrategy)):
            return ['bought [kWh]', 'sold [kWh]', 'offered [kWh]', 'used [kWh]', 'charge [%]']
        elif isinstance(self.area.strategy, LoadHoursStrategy):
            return ['desired energy [kWh]', 'deficit [kWh]']
        elif isinstance(self.area.strategy, PVStrategy):
            return ['produced [kWh]', 'not sold [kWh]', 'forecast [kWh]']
        return []

    def rows(self):
        markets = self.area.parent.past_markets
        return [self._row(slot, markets[slot]) for slot in markets]

    def _traded(self, market):
        return market.traded_energy[self.area.name]

    def _row(self, slot, market):
        return [slot, self._traded(market)] + self._specific_row(slot, market)

    def _specific_row(self, slot, market):
        if isinstance(self.area.strategy, FridgeStrategy):
            return [self.area.strategy.temp_history[slot]]
        elif isinstance(self.area.strategy, (StorageStrategy, NightStorageStrategy)):
            s = self.area.strategy.state
            return [market.bought_energy(self.area.name),
                    market.sold_energy(self.area.name),
                    s.offered_history[slot],
                    s.used_history[slot],
                    s.charge_history[slot]]
        elif isinstance(self.area.strategy, LoadHoursStrategy):
            desired = self.area.strategy.state.desired_energy[slot] / 1000
            return [desired, self._traded(market) + desired]
        elif isinstance(self.area.strategy, PVStrategy):
            produced = market.actual_energy_agg.get(self.area.name, 0)
            return [produced,
                    produced - self._traded(market),
                    self.area.strategy.energy_production_forecast[slot]]
        return []


def _export_area_flat(area, directory):
    data = ExportData.create(area)
    rows = data.rows()
    if rows:
        try:
            with open(_file_path(directory, area.slug), 'w') as csv_file:
                writer = csv.writer(csv_file)
                writer.writerow(data.labels())
                for row in rows:
                    writer.writerow(row)
        except Exception as ex:
            _log.error("Could not export area data: %s" % str(ex))


def _export_area_energy(area, directory):
    try:
        with open(_file_path(directory, "{}-trades".format(area.slug)), 'w') as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(("slot",) + Trade._csv_fields())
            for slot, market in area.past_markets.items():
                for trade in market.trades:
                    writer.writerow((slot, ) + trade._to_csv())
    except OSError:
        _log.exception("Could not export area trades")


def _export_overview(root_area, directory):
    markets = root_area.past_markets
    overview = {
        'avg_trade_price_history': [markets[slot].avg_trade_price for slot in markets]
    }
    try:
        directory.joinpath("overview.json").write_text(json.dumps(overview, indent=2))
    except Exception as ex:
        _log.error("Error when writing overview file: %s" % str(ex))
