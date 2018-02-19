import csv
import json
import logging
import pathlib
from collections import defaultdict

from d3a.models.market import Trade
from d3a.models.strategy.fridge import FridgeStrategy
from d3a.models.strategy.greedy_night_storage import NightStorageStrategy
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
                'avg trade price [€]',
                'min trade price [€]',
                'max trade price [€]',
                '# trades',
                'total energy traded [kWh]',
                'total trade volume [€]']

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
        return ['energy balance [kWh]'] + self._specific_labels()

    def _specific_labels(self):
        if isinstance(self.area.strategy, FridgeStrategy):
            return ['temperature [°C]']
        elif isinstance(self.area.strategy, (StorageStrategy, NightStorageStrategy)):
            return ['offered [kWh]', 'used [kWh]']
        return []

    def rows(self):
        markets = self.area.parent.past_markets
        return [self._row(slot, markets[slot]) for slot in markets]

    def _row(self, slot, market):
        return [market.traded_energy[self.area.name]] + self._specific_row(slot, market)

    def _specific_row(self, slot, market):
        if isinstance(self.area.strategy, FridgeStrategy):
            return [self.area.strategy.temp_history[slot]]
        elif isinstance(self.area.strategy, (StorageStrategy, NightStorageStrategy)):
            s = self.area.strategy.state
            return [s.offered_history[slot], s.used_history[slot]]
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


# Try evaluate current storage usage
class StorageData():
    def __init__(self):
        self.storage_Areas = defaultdict(set)
        self.storages = []
        self.market_capacities = defaultdict(
            dict)  # type: Dict[Pendulum, Dict[area.name, capacity]]

    def _get_storage_areas(self, area):
        for child in area.children:
            if child.strategy is not None and isinstance(child.stratetgy,
                                                         (StorageStrategy, NightStorageStrategy)):
                self.storage_Areas[area].add(child)

    def _export_storage_capacity(self):
        for area, children in self.storage_Areas.items():
            for market in area.markets:
                for trade in market.trades:
                    if trade.seller in children:
                        self.market_capacities[market.time_slot][trade.seller] -= \
                            trade.offer.energy
                    if trade.buyer in children:
                        self.market_capacities[market.time_slot][trade.buyer] += trade.offer.energy
