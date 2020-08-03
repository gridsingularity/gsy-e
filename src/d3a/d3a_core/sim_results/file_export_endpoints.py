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
from d3a.models.area import Area
from d3a.models.strategy.load_hours import LoadHoursStrategy, CellTowerLoadHoursStrategy
from d3a.models.strategy.predefined_load import DefinedLoadStrategy
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.strategy.pv import PVStrategy
from d3a.constants import FLOATING_POINT_TOLERANCE
from d3a.d3a_core.util import generate_market_slot_list, round_floats_for_ui, \
    area_name_from_area_or_iaa_name
from d3a_interface.constants_limits import ConstSettings
from d3a_interface.sim_results.aggregate_results import merge_energy_trade_profile_to_global
from copy import copy
from d3a.d3a_core.util import add_or_create_key


trade_profile_init_dict = {"sold_energy": {}, "bought_energy": {}}


def calculate_devices_sold_bought_energy(res_dict, market, time_slots):
    if market is None:
        return

    for trade in market.trades:
        trade_seller = area_name_from_area_or_iaa_name(trade.seller)
        trade_buyer = area_name_from_area_or_iaa_name(trade.buyer)

        if trade_seller not in res_dict["sold_energy"]:
            res_dict["sold_energy"][trade_seller] = {}
            res_dict["sold_energy"][trade_seller]["accumulated"] = dict(
                (time_slot, 0) for time_slot in time_slots)
        if trade_buyer not in res_dict["sold_energy"][trade_seller]:
            res_dict["sold_energy"][trade_seller][trade_buyer] = dict(
                (time_slot, 0) for time_slot in time_slots)
        if trade.offer.energy > FLOATING_POINT_TOLERANCE:
            # res_dict["sold_energy"][trade_seller]["accumulated"][market.time_slot] += \
            #     trade.offer.energy
            # res_dict["sold_energy"][trade_seller][trade_buyer][market.time_slot] += \
            #     trade.offer.energy
            add_or_create_key(res_dict["sold_energy"][trade_seller]["accumulated"],
                              market.time_slot, trade.offer.energy)
            add_or_create_key(res_dict["sold_energy"][trade_seller][trade_buyer],
                              market.time_slot, trade.offer.energy)

        if trade_buyer not in res_dict["bought_energy"]:
            res_dict["bought_energy"][trade_buyer] = {}
            res_dict["bought_energy"][trade_buyer]["accumulated"] = dict(
                (time_slot, 0) for time_slot in time_slots)
        if trade_seller not in res_dict["bought_energy"][trade_buyer]:
            res_dict["bought_energy"][trade_buyer][trade_seller] = dict(
                (time_slot, 0) for time_slot in time_slots)
        if trade.offer.energy > FLOATING_POINT_TOLERANCE:
            # res_dict["bought_energy"][trade_buyer]["accumulated"][market.time_slot] += \
            #     trade.offer.energy
            # res_dict["bought_energy"][trade_buyer][trade_seller][market.time_slot] += \
            #     trade.offer.energy
            add_or_create_key(res_dict["bought_energy"][trade_buyer]["accumulated"],
                              market.time_slot, trade.offer.energy)
            add_or_create_key(res_dict["bought_energy"][trade_buyer][trade_seller],
                              market.time_slot, trade.offer.energy)


class FileExportEndpoints:
    def __init__(self, should_export_plots):
        self._should_export_plots = should_export_plots
        self.traded_energy_profile = {}
        self.traded_energy_current = {}
        self.balancing_traded_energy = {}
        self.plot_stats = {}
        self.plot_balancing_stats = {}
        self.time_slots = []
        self.cumulative_offers = {}
        self.cumulative_bids = {}
        self.clearing = {}

    def __call__(self, area):
        if len(self.time_slots) == 0:
            self.time_slots = generate_market_slot_list(area)
        # Resetting traded energy before repopulating it
        # if self._should_export_plots:
        self.traded_energy_current = {}
        self._populate_area_children_data(area)
        self.traded_energy_current = self._round_energy_trade_profile(self.traded_energy_current)

    def _populate_area_children_data(self, area):
        if area.children:
            for child in area.children:
                self._populate_area_children_data(child)

        if self._should_export_plots:
            self.update_plot_stats(area)
        if area.children:
            self.update_sold_bought_energy(area)

    def generate_market_export_data(self, area, is_balancing_market):
        return ExportBalancingData(area) if is_balancing_market else ExportData.create(area)

    def update_sold_bought_energy(self, area: Area):
        if ConstSettings.GeneralSettings.KEEP_PAST_MARKETS:
            # TODO: deprecate this branch as KEEP_PAST_MARKETS should always be False
            self.traded_energy_profile[area.name] = trade_profile_init_dict
            calculate_devices_sold_bought_energy(self.traded_energy_profile[area.name],
                                                 area.current_market, self.time_slots)

            self.balancing_traded_energy[area.name] = trade_profile_init_dict
            if len(area.past_balancing_markets) > 0:
                calculate_devices_sold_bought_energy(self.balancing_traded_energy[area.name],
                                                     area.current_market, self.time_slots)
        else:
            # Calculates current market traded energy
            if area.current_market is not None:
                if area.name not in self.traded_energy_current:
                    self.traded_energy_current[area.name] = trade_profile_init_dict

                calculate_devices_sold_bought_energy(
                    self.traded_energy_current[area.name],
                    area.current_market, [area.current_market.time_slot])

                if area.name not in self.traded_energy_profile:
                    self.traded_energy_profile[area.name] = trade_profile_init_dict
                    calculate_devices_sold_bought_energy(self.traded_energy_profile[area.name],
                                                         area.current_market, self.time_slots)

                traded_energy_current_name = {area.name: self.traded_energy_current[area.name]}
                self.traded_energy_profile = merge_energy_trade_profile_to_global(
                    traded_energy_current_name, self.traded_energy_profile,
                    self.time_slots)
                # balancing energy
                if area.name not in self.balancing_traded_energy:
                    self.balancing_traded_energy[area.name] = trade_profile_init_dict
                if len(area.past_balancing_markets) > 0:
                    calculate_devices_sold_bought_energy(
                        self.balancing_traded_energy[area.name], area.current_balancing_market,
                        self.time_slots)

    @classmethod
    def _serialize_traded_energy_lists(cls, traded_energy, area_uuid):
        outdict = {}
        if area_uuid not in traded_energy:
            return outdict
        for direction in trade_profile_init_dict.keys():
            outdict[direction] = {}
            for seller, buyer_dict in traded_energy[area_uuid][direction].items():
                outdict[direction][seller] = {}
                for buyer, profile_dict in buyer_dict.items():
                    outdict[direction][seller][buyer] = copy(profile_dict)
        return outdict

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
        if ConstSettings.GeneralSettings.EXPORT_SUPPLY_DEMAND_PLOTS and self._should_export_plots:
            self._populate_plots_stats_for_supply_demand_curve(area)

    @classmethod
    def add_sold_bought_lists(cls, res_dict):
        for area_name in res_dict.keys():
            for ks in ("sold_energy", "bought_energy"):
                res_dict[area_name][ks + "_lists"] = \
                    dict((ki, {}) for ki in res_dict[area_name][ks].keys())
                for node in res_dict[area_name][ks].keys():
                    res_dict[area_name][ks + "_lists"][node]["slot"] = \
                        list(res_dict[area_name][ks][node]["accumulated"].keys())
                    res_dict[area_name][ks + "_lists"][node]["energy"] = \
                        list(res_dict[area_name][ks][node]["accumulated"].values())

    @classmethod
    def _round_energy_trade_profile(cls, profile):
        for k in profile.keys():
            for sold_bought in trade_profile_init_dict.keys():
                if sold_bought not in profile[k]:
                    continue
                for dev in profile[k][sold_bought].keys():
                    for target in profile[k][sold_bought][dev].keys():
                        for timestamp in profile[k][sold_bought][dev][target].keys():
                            profile[k][sold_bought][dev][target][timestamp] = round_floats_for_ui(
                                profile[k][sold_bought][dev][target][timestamp])
        return profile


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
        elif isinstance(self.area.strategy, (LoadHoursStrategy, DefinedLoadStrategy,
                                             DefinedLoadStrategy, CellTowerLoadHoursStrategy)):
            desired = self.area.strategy.state.desired_energy_Wh.get(slot, 0) / 1000
            return [desired, self._traded(market) + desired]
        elif isinstance(self.area.strategy, PVStrategy):
            produced = market.actual_energy_agg.get(self.area.name, 0)
            return [produced,
                    round(produced -
                          self.area.strategy.energy_production_forecast_kWh.get(slot, 0), 4),
                    self.area.strategy.energy_production_forecast_kWh.get(slot, 0)
                    ]
        return []
