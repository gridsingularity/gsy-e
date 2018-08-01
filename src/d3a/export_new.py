import csv
import logging
import pathlib
import os
import plotly as py
import plotly.graph_objs as go

from d3a.models.market import Trade
from d3a.models.strategy.fridge import FridgeStrategy
from d3a.models.strategy.greedy_night_storage import NightStorageStrategy
from d3a.models.strategy.load_hours_fb import LoadHoursStrategy, CellTowerLoadHoursStrategy
from d3a.models.strategy.permanent import PermanentLoadStrategy
from d3a.models.strategy.predefined_load import DefinedLoadStrategy
from d3a.models.strategy.pv import PVStrategy
from d3a.models.strategy.predefined_pv import PVPredefinedStrategy, PVUserProfileStrategy
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.area import Area

import dill
import pint
from d3a.models.strategy import ureg

from functools import reduce
import operator

_log = logging.getLogger(__name__)


def getfromdict(dataDict, mapList):
    return reduce(operator.getitem, mapList, dataDict)


def setindict(dataDict, mapList, value):
    getfromdict(dataDict, mapList[:-1])[mapList[-1]] = value


class ExportAndPlot:

    def __init__(self, root_area: Area, path: str, subdir: str):
        self.trades = {}
        self.stats = {}
        self.iaa_trades = {}
        self.area = root_area
        self.hierarchy_list = []
        self.hierarchy = {}
        self.level_dict = {1: [self.area.name]}

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

        self._get_hierarchy()
        self.export_area_with_children(self.area, self.directory)

        self._export_iaa_energy(self.area, self.directory)

        self.plot_ess_profile(self.area)
        self.plot_all_soc_history()
        self.plot_all_unmatched_loads()

        self.plot_traded_energy_history_all_knots(self.area)

        level_list = list(self.level_dict.keys())
        level_list.sort()
        for level in level_list[:-1]:
            self._plot_avg_trade_price(level)
        for level in level_list:
            self._plot_traded_energy_history_level(level)

    @staticmethod
    def _file_path(directory: dir, slug: str):
        file_name = ("%s.csv" % slug).replace(' ', '_')
        return directory.joinpath(file_name).as_posix()

    def plot_ess_profile(self, area):
        # TODO: Please review try: except:

        for child in area.children:
            if child.children:
                self.plot_ess_profile(child)
            else:
                try:
                    cap = child.strategy.state.capacity
                    cap += 1
                    self._plot_ess_profile(child.slug)
                except KeyError:
                    continue

    def _plot_ess_profile(self, area_name):
        data = list()
        barmode = 'relative'
        xtitle = 'Time'
        ytitle = 'Energy (kWh)'
        title = 'ESS Energy Trade ({})'.format(area_name)
        key = 'energy traded [kWh]'

        hiss1 = BarGraph(self.stats[area_name], key)
        hiss1.graph_value("ESS History")
        traceiss1 = go.Bar(x=list(hiss1.umHours.keys()),
                           y=list(hiss1.umHours.values()),
                           name=area_name)
        data.append(traceiss1)

        if not data:
            return

        output_file = os.path.join(self.plot_dir, 'ess_trade_{}.html'.format(area_name))
        BarGraph.plot_bar_graph(barmode, title, xtitle, ytitle, data, output_file)

    def _house_trade_history(self, path, barmode, xtitle, ytitle):
        """
        TODO: Please implement me!
        """
        pass

    def plot_traded_energy_history_all_knots(self, area: Area):
        for child in area.children:
            if child.children:
                self._plot_traded_energy_history_knots(child.slug)
                self.plot_traded_energy_history_all_knots(child)

    def _plot_traded_energy_history_knots(self, area_name: str):
        data = list()
        barmode = "relative"
        xtitle = 'Time'
        ytitle = 'Energy (kWh)'
        key = 'total energy traded [kWh]'
        title = 'Energy Profile Level {}'.format(area_name)

        higl = BarGraph(self.stats[area_name.lower()], key)
        higl.graph_value("Energy Profile")
        traceigl = go.Bar(x=list(higl.umHours.keys()),
                          y=list(higl.umHours.values()),
                          name=area_name)

        data.append(traceigl)
        if not data:
            return
        if all([len(da.y) == 0 for da in data]):
            return
        output_file = os.path.join(self.plot_dir,
                                   'traded_energy_profile_{}.html'.format(area_name))
        BarGraph.plot_bar_graph(barmode, title, xtitle, ytitle, data, output_file)

    def _plot_traded_energy_history_level(self, level: int):
        data = list()
        barmode = "relative"
        xtitle = 'Time'
        ytitle = 'Energy (kWh)'
        key = 'energy traded [kWh]'
        title = 'Energy Profile Level {}'.format(level)
        for area_name in self.level_dict[level]:

            higl = BarGraph(self.stats[area_name.lower()], key)
            higl.graph_value("Energy Profile")
            traceigl = go.Bar(x=list(higl.umHours.keys()),
                              y=list(higl.umHours.values()),
                              name=area_name)

            data.append(traceigl)
        if not data:
            return
        if all([len(da.y) == 0 for da in data]):
            return
        output_file = os.path.join(self.plot_dir,
                                   'traded_energy_profile_level{}.html'.format(level))
        BarGraph.plot_bar_graph(barmode, title, xtitle, ytitle, data, output_file)

    def _prepare_hierarchy(self, area: Area, address: str):
        for child in area.children:
            node = os.path.join(address, child.slug)
            self.hierarchy_list.append(node)
            if child.children:
                self._prepare_hierarchy(child, node)

    def _get_levels(self):

        for li in self.hierarchy_list:
            li_list = li.split("/")
            level = len(li_list)
            if level in self.level_dict.keys():
                self.level_dict[level].append(li_list[-1])
            else:
                self.level_dict[level] = [li_list[-1]]

    def _get_hierarchy(self):

        self._prepare_hierarchy(self.area, self.area.name)
        self.hierarchy_list.sort(key=len)
        self._get_levels()
        self.hierarchy[self.area.name] = {}
        for node in self.hierarchy_list:
            address = node.split("/")
            try:
                getfromdict(self.hierarchy, address)
            except KeyError:
                setindict(self.hierarchy, address, {"adress": node})

    def plot_all_unmatched_loads(self):

        unmatched_key = 'deficit [kWh]'
        load_list = [key for key, value in self.stats.items() if unmatched_key in value]
        data = list()
        title = 'Devices Un-matched Loads'
        xtitle = 'Time'
        ytitle = 'Energy (kWh)'
        barmode = 'bar'

        for li in load_list:
            hict = BarGraph(self.stats[li], unmatched_key)
            if sum(hict.dataset[unmatched_key]) < 1e-10:
                continue
            hict.graph_value("Unmatched Loads")
            traceict = go.Bar(x=list(hict.umHours.keys()),
                              y=list(hict.umHours.values()),
                              name=li)
            data.append(traceict)
            output_file = os.path.join(self.plot_dir, 'unmatched_loads_all.html')
            BarGraph.plot_bar_graph(barmode, title, xtitle, ytitle, data, output_file)

    def plot_all_soc_history(self):

        storage_key = 'charge [%]'
        storage_list = [key for key, value in self.stats.items() if storage_key in value]
        data = list()
        barmode = "relative"
        title = 'ESS SOC'
        xtitle = 'Time'
        ytitle = 'charge [%]'

        for si in storage_list:
            chss1 = BarGraph(self.stats[si], storage_key)
            chss1.graph_value("SOC History")
            tracechss1 = go.Scatter(x=list(chss1.umHours.keys()),
                                    y=list(chss1.umHours.values()),
                                    name=si)
            data.append(tracechss1)
        output_file = os.path.join(self.plot_dir, 'ess_soc_all_history.html')
        BarGraph.plot_bar_graph(barmode, title, xtitle, ytitle, data, output_file)

    def export_area_with_children(self, area, directory):
        if area.children:
            subdirectory = pathlib.Path(directory, area.slug.replace(' ', '_'))
            subdirectory.mkdir(exist_ok=True, parents=True)
            for child in area.children:
                self.export_area_with_children(child, subdirectory)
        self.stats[area.slug.replace(' ', '_')] = self._export_area_flat(area, directory)
        if area.children:
            self.trades[area.slug.replace(' ', '_')] = self._export_area_energy(area, directory)

    def _export_area_energy(self, area: Area, directory: str):
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

    def _export_iaa_energy(self, area: Area, directory: dir):
        """
        Exports IAA trades (*-external-trades.csv)
        TODO: Keep working on me
        """
        # house_level = list(self.level_dict.keys())
        # house_level.sort()
        # valid_iaa_list = self.level_dict[house_level[-2]]
        try:
            for i, child in enumerate(area.children, 1):
                if child.children:
                    with open(self._file_path(
                            directory, "{}-external-trades".format(child.slug)), 'w') as csv_file:
                        writer = csv.writer(csv_file)
                        labels = ("slot", "rate [ct./kWh]", "energy [kWh]")
                        writer.writerow(labels)
                        out_dict = dict((key, []) for key in labels)
                        for slot, market in area.past_markets.items():
                            for trade in market.trades:
                                if "IAA" in trade.buyer:
                                    row = (slot, ) + \
                                          (round(trade.offer.price/trade.offer.energy, 4),
                                           (trade.offer.energy*(-1)))
                                    writer.writerow(row)
                                    for ii, ri in enumerate(labels):
                                        out_dict[ri].append(row[ii])
                                else:
                                    pass
                    self._export_iaa_energy(child, directory)
        except OSError:
            _log.exception("Could not export area trades")

    def _export_area_flat(self, area: Area, directory: dir):
        """
        Exports stats (*.csv files)
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

    def _plot_avg_trade_price(self, level: int):
        data = list()
        barmode = 'bar'
        xtitle = "Time"
        ytitle = "Price [ct./kWh]"
        key = 'avg trade rate [ct./kWh]'
        title = 'Average Trade Price Level {}'.format(level)
        for area_name in self.level_dict[level]:
            higap = BarGraph(self.stats[area_name.lower()], key)
            higap.graph_value("Average Trade Price")
            traceigap = go.Scatter(x=list(higap.umHours.keys()),
                                   y=list(higap.umHours.values()),
                                   name=area_name.lower())
            data.append(traceigap)
        if all([len(da.y) == 0 for da in data]):
            return
        output_file = os.path.join(self.plot_dir, 'average_trade_price_level{}.html'.format(level))
        BarGraph.plot_bar_graph(barmode, title, xtitle, ytitle, data, output_file)


class ExportData:
    def __init__(self, area):
        self.area = area

    @staticmethod
    def create(area):
        return ExportUpperLevelData(area) if len(area.children) > 0 else ExportLeafData(area)


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
                                             DefinedLoadStrategy, PermanentLoadStrategy,
                                             CellTowerLoadHoursStrategy)):
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
        elif isinstance(self.area.strategy, (LoadHoursStrategy, DefinedLoadStrategy,
                                             DefinedLoadStrategy, PermanentLoadStrategy,
                                             CellTowerLoadHoursStrategy)):
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
    def __init__(self, dataset: dict, key: str):
        self.key = key
        self.dataset = dataset
        self.umHours = dict()

    def graph_value(self, graph_name):
        try:
            self.dataset[self.key]
        except KeyError:
            pass
        else:
            for de in range(len(self.dataset[self.key])):
                if self.dataset[self.key][de] != 0:
                    self.umHours[self.dataset['slot'][de]] = round(self.dataset[self.key][de], 5)

    @staticmethod
    def plot_bar_graph(barmode: str, title: str, xtitle: str, ytitle: str, data, iname: str):
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
