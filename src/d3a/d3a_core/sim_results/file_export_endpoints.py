"""
Copyright 2018 Grid Singularity
This file is part of D3A.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
from d3a.models.strategy.load_hours import LoadHoursStrategy
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.strategy.pv import PVStrategy
from d3a_interface.constants_limits import ConstSettings


class FileExportEndpoints:
    def __init__(self):
        self.plot_stats = {}
        self.plot_balancing_stats = {}
        self.cumulative_offers = {}
        self.cumulative_bids = {}
        self.clearing = {}

    def __call__(self, area):
        self._populate_area_children_data(area)

    def _populate_area_children_data(self, area):
        if area.children:
            for child in area.children:
                self._populate_area_children_data(child)
        self.update_plot_stats(area)

    @staticmethod
    def generate_market_export_data(area, is_balancing_market):
        return ExportBalancingData(area) if is_balancing_market else ExportData.create(area)

    def _get_stats_from_market_data(self, out_dict, area, balancing):
        data = self.generate_market_export_data(area, balancing)
        if area.slug not in out_dict:
            out_dict[area.slug] = dict((key, []) for key in data.labels())
        for row in data.rows():
            for ii, label in enumerate(data.labels()):
                out_dict[area.slug][label].append(row[ii])

    def _populate_plots_stats_for_supply_demand_curve(self, area):
        if ConstSettings.IAASettings.MARKET_TYPE == 3:
            if len(area.past_markets) == 0:
                return
            market = area.past_markets[-1]
            if area.slug not in self.cumulative_offers:
                self.cumulative_offers[area.slug] = {}
                self.cumulative_bids[area.slug] = {}
                self.clearing[area.slug] = {}
            if market.time_slot not in self.cumulative_offers[area.slug]:
                self.cumulative_offers[area.slug][market.time_slot] = {}
                self.cumulative_bids[area.slug][market.time_slot] = {}
                self.clearing[area.slug][market.time_slot] = {}
            self.cumulative_offers[area.slug][market.time_slot] = market.state.cumulative_offers
            self.cumulative_bids[area.slug][market.time_slot] = market.state.cumulative_bids
            self.clearing[area.slug][market.time_slot] = market.state.clearing

    def update_plot_stats(self, area):
        self._get_stats_from_market_data(self.plot_stats, area, False)
        if ConstSettings.BalancingSettings.ENABLE_BALANCING_MARKET:
            self._get_stats_from_market_data(self.plot_balancing_stats, area, True)
        if ConstSettings.GeneralSettings.EXPORT_SUPPLY_DEMAND_PLOTS:
            self._populate_plots_stats_for_supply_demand_curve(area)


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
                'total trade volume [EURO ct.]']

    def rows(self):
        return [self._row(m.time_slot, m) for m in self.area.past_markets]

    def _row(self, slot, market):
        return [slot,
                market.avg_trade_price,
                market.min_trade_price,
                market.max_trade_price,
                len(market.trades),
                sum(trade.offer.energy for trade in market.trades),
                sum(trade.offer.price for trade in market.trades)]


class ExportBalancingData:
    def __init__(self, area):
        self.area = area

    def labels(self):
        return ['slot',
                'avg supply balancing trade rate [ct./kWh]',
                'avg demand balancing trade rate [ct./kWh]']

    def rows(self):
        return [self._row(m.time_slot, m) for m in self.area.past_balancing_markets]

    def _row(self, slot, market):
        return [slot,
                market.avg_supply_balancing_trade_rate,
                market.avg_demand_balancing_trade_rate]


class ExportLeafData(ExportData):
    def __init__(self, area):
        super(ExportLeafData, self).__init__(area)

    def labels(self):
        return ['slot',
                'energy traded [kWh]',
                ] + self._specific_labels()

    def _specific_labels(self):
        if isinstance(self.area.strategy, StorageStrategy):
            return ['bought [kWh]', 'sold [kWh]', 'charge [kWh]', 'offered [kWh]', 'charge [%]']
        elif isinstance(self.area.strategy, LoadHoursStrategy):
            return ['desired energy [kWh]', 'deficit [kWh]']
        elif isinstance(self.area.strategy, PVStrategy):
            return ['produced to trade [kWh]', 'not sold [kWh]', 'forecast / generation [kWh]']
        return []

    def rows(self):
        return [self._row(m.time_slot, m) for m in self.area.parent.past_markets]

    def _traded(self, market):
        return market.traded_energy[self.area.name] \
            if self.area.name in market.traded_energy else 0

    def _row(self, slot, market):
        return [slot,
                self._traded(market),
                ] + self._specific_row(slot, market)

    def _specific_row(self, slot, market):
        if isinstance(self.area.strategy, StorageStrategy):
            s = self.area.strategy.state
            return [market.bought_energy(self.area.name),
                    market.sold_energy(self.area.name),
                    s.charge_history_kWh[slot],
                    s.offered_history[slot],
                    s.charge_history[slot]]
        elif isinstance(self.area.strategy, (LoadHoursStrategy)):
            desired = self.area.strategy.state.get_desired_energy_Wh(slot) / 1000
            return [desired, self._traded(market) + desired]
        elif isinstance(self.area.strategy, PVStrategy):
            produced = self.area.strategy.state.get_available_energy_kWh(slot, 0.0)
            forecasted = self.area.strategy.state.get_energy_production_forecast_kWh(slot, 0.0)
            curtailed = round(produced - forecasted, 4)
            return [produced, curtailed, forecasted]
        return []
