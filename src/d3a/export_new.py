import csv
import logging
import pathlib
import os
import plotly as py
import plotly.graph_objs as go

from d3a.models.market import Trade
from d3a.models.strategy.fridge import FridgeStrategy
from d3a.models.strategy.greedy_night_storage import NightStorageStrategy
from d3a.models.strategy.load_hours_fb import LoadHoursStrategy
from d3a.models.strategy.permanent import PermanentLoadStrategy
from d3a.models.strategy.predefined_load import DefinedLoadStrategy
from d3a.models.strategy.pv import PVStrategy
from d3a.models.strategy.predefined_pv import PVPredefinedStrategy, PVUserProfileStrategy
from d3a.models.strategy.storage import StorageStrategy

import dill
import pint
from d3a.models.strategy import ureg

_log = logging.getLogger(__name__)


class ExportAndPlot:

    def __init__(self, root_area, path, subdir):
        self.trades = {}
        self.rates = {}
        self.area = root_area

        try:
            if path is not None:
                path = os.path.abspath(path)
            self.directory = pathlib.Path(path or "~/d3a-simulation", subdir).expanduser()
            self.directory.mkdir(exist_ok=True, parents=True)
        except Exception as ex:
            _log.error("Could not open directory for csv exports: %s" % str(ex))
            return

        self.plot_dir = os.path.join(self.directory, 'plot')
        if not os.path.exists(self.plot_dir):
            os.makedirs(self.plot_dir)

        self.export()

    def export(self):
        """Export all data of the finished simulation in one CSV file per area."""

        self.export_area_with_children(self.area, self.directory)
        # _export_iaa_energy(root_area, directory)

        self.plot_all_soc_history()
        self.plot_all_unmatched_loads()
        self.plot_all_avg_trade_price(self.area)

    def _file_path(self, directory, slug):
        file_name = ("%s.csv" % slug).replace(' ', '_')
        return directory.joinpath(file_name).as_posix()

    def plot_all_unmatched_loads(self):

        unmatched_key = 'deficit [kWh]'
        load_list = [key for key, value in self.rates.items() if unmatched_key in value]
        data = list()
        title = 'Devices Un-matched Loads'
        xtitle = 'Time'
        ytitle = 'Energy (kWh)'
        barmode = 'bar'

        for li in load_list:
            hict = BarGraph(self.rates[li], unmatched_key)
            print(li, sum(hict.dataset[unmatched_key]))
            if sum(hict.dataset[unmatched_key]) < 1e-10:
                continue
            hict.graph_value("Unmatched Loads")
            traceict = go.Bar(x=list(range(0, 24)),
                              y=list(hict.umHours.values()),
                              name=li)
            data.append(traceict)
            output_file = os.path.join(self.plot_dir, 'unmatched_loads_all.html')
            BarGraph.plot_bar_graph(barmode, title, xtitle, ytitle, data, output_file)

    def plot_all_soc_history(self):

        storage_key = 'charge [%]'
        storage_list = [key for key, value in self.rates.items() if storage_key in value]
        data = list()
        barmode = "relative"
        title = 'ESS SOC'
        xtitle = 'Time'
        ytitle = 'charge [%]'

        for si in storage_list:
            chss1 = BarGraph(self.rates[si], storage_key)
            chss1.graph_value("SOC History")
            tracechss1 = go.Scatter(x=list(range(0, 24)),
                                    y=list(chss1.umHours.values()),
                                    name=si)
            data.append(tracechss1)
        output_file = os.path.join(self.plot_dir, 'ESS_SOC_all_history.html')
        BarGraph.plot_bar_graph(barmode, title, xtitle, ytitle, data, output_file)

    def plot_all_avg_trade_price(self, area):
        for child in area.children:
            if child.children:
                self._plot_avg_trade_price(child.slug)
                self.plot_all_avg_trade_price(child)

    def export_area_with_children(self, area, directory):
        if area.children:
            subdirectory = pathlib.Path(directory, area.slug.replace(' ', '_'))
            subdirectory.mkdir(exist_ok=True, parents=True)
            for child in area.children:
                self.export_area_with_children(child, subdirectory)
        self.rates[area.slug.replace(' ', '_')] = self._export_area_flat(area, directory)
        if (area.children):
            self.trades[area.slug.replace(' ', '_')] = self._export_area_energy(area, directory)

    def _export_area_energy(self, area, directory):
        """
        Exports files containing individual trades  (*-trades.csv  files)
        """
        try:
            with open(self._file_path(directory, "{}-trades".format(area.slug)), 'w') as csv_file:
                writer = csv.writer(csv_file)
                labels = ("slot",) + Trade._csv_fields()
                writer.writerow(labels)
                out_dict = dict((key, []) for key in labels)
                for slot, market in area.past_markets.items():
                    for trade in market.trades:
                        row = (slot, ) + trade._to_csv()
                        writer.writerow(row)
                        for ii, lab in enumerate(("slot",) + Trade._csv_fields()):
                            out_dict[lab].append(row[ii])
            return out_dict
        except OSError:
            _log.exception("Could not export area trades")

    def _export_iaa_energy(self, area, directory):
        """
        Exports IAA trades (*-external-trades.csv)
        TODO: Check if they are working or used art all
        """
        try:
            for i, child in enumerate(area.children, 1):
                if child.children:
                    with open(self._file_path(
                            directory, "{}-external-trades".format(child.slug)), 'w') as csv_file:
                        writer = csv.writer(csv_file)
                        writer.writerow(("slot", "rate [ct./kWh]", "energy [kWh]"))
                        for slot, market in area.past_markets.items():
                            for trade in market.trades:
                                if trade.buyer == 'IAA House {}'.format(i):
                                    row = (slot, ) + \
                                          (round(trade.offer.price/trade.offer.energy, 4),
                                           (trade.offer.energy*(-1)))
                                    writer.writerow(row)
                                elif trade.seller == 'IAA House {}'.format(i):
                                    row = (slot,) + \
                                          (round(trade.offer.price / trade.offer.energy, 4),
                                           trade.offer.energy)
                                    writer.writerow(row)
                                else:
                                    pass

        except OSError:
            _log.exception("Could not export area trades")

    def _export_area_flat(self, area, directory):
        """
        Exports rates (*.csv files)
        """
        data = ExportData.create(area)
        rows = data.rows()
        if rows:
            try:
                with open(self._file_path(directory, area.slug), 'w') as csv_file:
                    writer = csv.writer(csv_file)
                    labels = data.labels()
                    writer.writerow(labels)
                    out_dict = dict((key, []) for key in labels)
                    for row in rows:
                        writer.writerow(row)
                        for ii, ri in enumerate(labels):
                            out_dict[ri].append(row[ii])
                return out_dict
            except Exception as ex:
                _log.error("Could not export area data: %s" % str(ex))

    def _plot_avg_trade_price(self, area_name):
        data = list()
        barmode = 'bar'
        xtitle = "Time"
        ytitle = "Price [ct./kWh]"
        key = 'avg trade rate [ct./kWh]'
        title = 'Average Trade Price ({})'.format(area_name)
        higap = BarGraph(self.rates[area_name], key)
        higap.graph_value("Average Trade Price")
        traceigap = go.Scatter(x=list(range(0, 24)),
                               y=list(higap.umHours.values()),
                               name='Grid')
        data.append(traceigap)
        output_file = os.path.join(self.plot_dir, 'average_trade_price_{}.html'.format(area_name))
        BarGraph.plot_bar_graph(barmode, title, xtitle, ytitle, data, output_file)


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
                'avg trade rate [ct./kWh]',
                'min trade rate [ct./kWh]',
                'max trade rate [ct./kWh]',
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
        return ['slot', 'energy traded [kWh]'] + self._specific_labels()

    def _specific_labels(self):
        # TODO: review the strategies
        if isinstance(self.area.strategy, FridgeStrategy):
            return ['temperature [°C]']
        elif isinstance(self.area.strategy, (StorageStrategy, NightStorageStrategy)):
            return ['bought [kWh]', 'sold [kWh]', 'energy balance [kWh]', 'offered [kWh]',
                    'used [kWh]', 'charge [%]', 'stored [kWh]']
        elif isinstance(self.area.strategy, (LoadHoursStrategy, DefinedLoadStrategy,
                                             DefinedLoadStrategy, PermanentLoadStrategy)):
            return ['desired energy [kWh]', 'deficit [kWh]']
        elif isinstance(self.area.strategy, (PVStrategy, PVPredefinedStrategy,
                                             PVUserProfileStrategy)):
            return ['produced to trade [kWh]', 'not sold [kWh]', 'forecast / generation [kWh]']
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
            charge = s.charge_history[slot]
            stored = '-' if charge == '-' else 0.01 * charge * s.capacity
            return [market.bought_energy(self.area.name),
                    market.sold_energy(self.area.name),
                    s.charge_history_kWh[slot],
                    s.offered_history[slot],
                    s.used_history[slot],
                    charge,
                    stored]
        elif isinstance(self.area.strategy, (LoadHoursStrategy, DefinedLoadStrategy)):
            desired = self.area.strategy.state.desired_energy[slot] / 1000
            return [desired, self._traded(market) + desired]
        elif isinstance(self.area.strategy, PVStrategy):
            produced = market.actual_energy_agg.get(self.area.name, 0)
            return [produced,
                    round(produced - self._traded(market), 4),
                    self.area.strategy.energy_production_forecast_kWh[slot] *
                    self.area.strategy.panel_count
                    ]
        return []


class BarGraph:
    def __init__(self, dataset, key):
        self.key = key
        self.dataset = dataset
        self.umHours = dict()

    def graph_value(self, graph_name):
        try:
            self.dataset[self.key]
        except KeyError:
            _log.error("Error during generating plot for " + str(graph_name) +
                       ": Key not found (" + str(self.key) + ")")
        else:
            for de in range(len(self.dataset[self.key])):
                if self.dataset[self.key][de] != 0:
                    self.umHours[self.dataset['slot'][de]] = round(self.dataset[self.key][de], 5)

    @staticmethod
    def plot_bar_graph(barmode, title, xtitle, ytitle, data, iname):
        layout = go.Layout(
            barmode=barmode,
            title=title,
            yaxis=dict(
                title=ytitle
            ),
            xaxis=dict(
                title=xtitle
            ),
            font=dict(
                size=16
            )
        )

        fig = go.Figure(data=data, layout=layout)
        py.offline.plot(fig, filename=iname, auto_open=False)


if __name__ == "__main__":

    pint.set_application_registry(ureg)
    simulation_data = dill.load(
        open("/Users/hannesd/d3a-simulation/d3a306/saved-state_20180731T174306.pickle", "rb"))

    sim_path = "/Users/hannesd/d3a-simulation/d3a306/"
    ExportAndPlot(simulation_data.area, sim_path, "")
