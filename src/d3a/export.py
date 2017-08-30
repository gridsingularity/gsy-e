import csv
import json
import logging
import pathlib
from collections import defaultdict

from d3a.models.strategy.greedy_night_storage import NightStorageStrategy
from d3a.models.strategy.storage import StorageStrategy

_log = logging.getLogger(__name__)


def export(root_area, path, file_prefix):
    """Export all data of the finished simulation in one CSV file per area."""
    try:
        directory = pathlib.Path(path or "~/d3a-simulation").expanduser()
        directory.mkdir(exist_ok=True)
    except Exception as ex:
        _log.error("Could not open directory for csv exports: %s" % str(ex))
        return
    _export_area_with_children(root_area, directory, file_prefix)
    _export_overview(root_area, directory, file_prefix)


def _export_area_with_children(area, directory, prefix):
    for child in area.children:
        _export_area_with_children(child, directory, prefix)
    _export_area_flat(area, directory, prefix)


def _file_path(directory, prefix, slug):
    file_name = ("%s_%s.csv" % (prefix, slug)).replace(' ', '_')
    return directory.joinpath(file_name).as_posix()


_labels = ['slot',
           'avg trade price [€]',
           'min trade price [€]',
           'max trade price [€]',
           '# trades',
           'total energy traded [kWh]',
           'total trade volume [€]']


def _market_row(slot, market):
    return [slot,
            market.avg_trade_price,
            market.min_trade_price,
            market.max_trade_price,
            len(market.trades),
            sum(trade.offer.energy for trade in market.trades),
            sum(trade.offer.price for trade in market.trades)]


def _export_area_flat(area, directory, prefix):
    try:
        with open(_file_path(directory, prefix, area.slug), 'w') as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(_labels)
            for slot in area.past_markets:
                writer.writerow(_market_row(slot, area.past_markets[slot]))
    except Exception as ex:
        _log.error("Could not export area data: %s" % str(ex))


def _export_overview(root_area, directory, prefix):
    overview = {  # TODO
    }
    try:
        directory.joinpath("%s_overview.json" % prefix).write_text(json.dumps(overview, indent=2))
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
