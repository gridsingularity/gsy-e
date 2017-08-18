import csv
from logging import getLogger

from d3a.model.area import Area


def export(root_area, file_prefix):
    """Export all data of the finished simulation in one CSV file per area."""
    _export_area_with_children(root_area, file_prefix)


def _export_area_with_children(area, file_prefix):
    for child in area.children:
        _export_area_with_children(child, file_prefix)
    _export_area_flat(area, file_prefix)


def _file_name(prefix, slug):
    return "%s_%s"%(prefix, slug.replace(' ', '_'))


_labels = ['slot',
           'avg trade price',
           'min trade price',
           'max trade price',
           '# trades',
           '# offers',
           'total energy traded',
           'total trade volume']


def _market_row(slot, market):
    return [slot,
            market.avg_trade_price,
            market.min_trade_price,
            market.max_trade_price,
            len(self.trades),
            len(self.offers) + len(self.trades),
            sum(trade.energy for trade in self.trades),
            sum(trade.price for trade in self.trades)]


def _export_area_flat(area, file_prefix):
    try:
        with open(_file_name(file_prefix, area.slug), 'wb') as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(_labels)
            for slot in area.past_markets:
                writer.writerow(_market_row(slot, area.past_markets[slot]))
            for slot in area.markets:
                writer.writerow(_market_row(slot, area.markets[slot]))
    except Exception as ex:
        log = getLogger(__name__)
        log.error("Could not export area data: %s" % str(ex))
