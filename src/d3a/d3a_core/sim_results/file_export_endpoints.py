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
from slugify import slugify
from d3a.models.area import Area
from d3a.models.strategy.load_hours import LoadHoursStrategy, CellTowerLoadHoursStrategy
from d3a.models.strategy.predefined_load import DefinedLoadStrategy
from d3a.models.strategy.storage import StorageStrategy
from d3a.d3a_core.sim_results.area_statistics import _is_house_node, \
    _is_load_node, _is_prosumer_node
from d3a.models.strategy.pv import PVStrategy
from d3a.models.strategy.commercial_producer import CommercialStrategy
from d3a.models.strategy.finite_power_plant import FinitePowerPlant
from d3a.d3a_core.util import convert_datetime_to_str_keys
from d3a.constants import FLOATING_POINT_TOLERANCE
from d3a.d3a_core.util import generate_market_slot_list
from d3a_interface.constants_limits import ConstSettings


class FileExportEndpoints:
    def __init__(self):
        self.traded_energy = {}
        self.traded_energy_profile = {}
        self.traded_energy_profile_redis = {}
        self.balancing_traded_energy = {}
        self.plot_stats = {}
        self.plot_balancing_stats = {}
        self.buyer_trades = {}
        self.seller_trades = {}
        self.time_slots = []
        self.cumulative_offers = {}
        self.cumulative_bids = {}
        self.clearing = {}

    def __call__(self, area):
        self.time_slots = generate_market_slot_list(area)
        self._populate_area_children_data(area)

    def _populate_area_children_data(self, area):
        if area.children:
            for child in area.children:
                self._populate_area_children_data(child)
        self.update_plot_stats(area)
        self._get_buyer_seller_trades(area)
        if area.children:
            self.update_sold_bought_energy(area)

    def generate_market_export_data(self, area, is_balancing_market):
        return ExportBalancingData(area) if is_balancing_market else ExportData.create(area)

    def update_sold_bought_energy(self, area: Area):
        if ConstSettings.GeneralSettings.KEEP_PAST_MARKETS:
            self.traded_energy[area.uuid] = \
                self._calculate_devices_sold_bought_energy_past_markets(area, area.past_markets)
            self.traded_energy[area.name] = self.traded_energy[area.uuid]
            self.balancing_traded_energy[area.name] = \
                self._calculate_devices_sold_bought_energy_past_markets(
                    area, area.past_balancing_markets)
        else:
            if area.uuid not in self.traded_energy:
                self.traded_energy[area.uuid] = {"sold_energy": {}, "bought_energy": {}}
            self._calculate_devices_sold_bought_energy(self.traded_energy[area.uuid],
                                                       area.current_market)
            self.traded_energy[area.name] = self.traded_energy[area.uuid]
            if area.name not in self.balancing_traded_energy:
                self.balancing_traded_energy[area.name] = {"sold_energy": {}, "bought_energy": {}}
            if len(area.past_balancing_markets) > 0:
                self._calculate_devices_sold_bought_energy(self.balancing_traded_energy[area.name],
                                                           area.current_balancing_market)

        self.balancing_traded_energy[area.uuid] = self.balancing_traded_energy[area.name]
        self.traded_energy_profile_redis[area.uuid] = self._serialize_traded_energy_lists(area)
        self.traded_energy_profile[area.slug] = self.traded_energy_profile_redis[area.uuid]

    def _serialize_traded_energy_lists(self, area):
        outdict = {}
        for direction in ["sold_energy", "bought_energy"]:
            outdict[direction] = {}
            for seller, buyer_dict in self.traded_energy[area.uuid][direction].items():
                outdict[direction][seller] = {}
                for buyer, profile_dict in buyer_dict.items():
                    outdict[direction][seller][buyer] = convert_datetime_to_str_keys(
                        profile_dict, {}, ui_format=True
                    )
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
        self._get_stats_from_market_data(self.plot_balancing_stats, area, True)
        self._populate_plots_stats_for_supply_demand_curve(area)

    def _calculate_devices_sold_bought_energy(self, res_dict, market):
        if market is None:
            return

        for trade in market.trades:
            trade_seller = trade.seller[4:] if trade.seller.startswith("IAA ") \
                else trade.seller
            trade_buyer = trade.buyer[4:] if trade.buyer.startswith("IAA ") \
                else trade.buyer

            if trade_seller not in res_dict["sold_energy"]:
                res_dict["sold_energy"][trade_seller] = {}
                res_dict["sold_energy"][trade_seller]["accumulated"] = dict(
                        (time_slot, 0) for time_slot in self.time_slots)
            if trade_buyer not in res_dict["sold_energy"][trade_seller]:
                res_dict["sold_energy"][trade_seller][trade_buyer] = dict(
                        (time_slot, 0) for time_slot in self.time_slots)
            if trade.offer.energy > FLOATING_POINT_TOLERANCE:
                res_dict["sold_energy"][trade_seller]["accumulated"][market.time_slot] += \
                    trade.offer.energy
                res_dict["sold_energy"][trade_seller][trade_buyer][market.time_slot] += \
                    trade.offer.energy

            if trade_buyer not in res_dict["bought_energy"]:
                res_dict["bought_energy"][trade_buyer] = {}
                res_dict["bought_energy"][trade_buyer]["accumulated"] = dict(
                        (time_slot, 0) for time_slot in self.time_slots)
            if trade_seller not in res_dict["bought_energy"][trade_buyer]:
                res_dict["bought_energy"][trade_buyer][trade_seller] = dict(
                        (time_slot, 0) for time_slot in self.time_slots)
            if trade.offer.energy > FLOATING_POINT_TOLERANCE:
                res_dict["bought_energy"][trade_buyer]["accumulated"][market.time_slot] += \
                    trade.offer.energy
                res_dict["bought_energy"][trade_buyer][trade_seller][market.time_slot] += \
                    trade.offer.energy

        self._add_sold_bought_lists(res_dict)

    @classmethod
    def _add_sold_bought_lists(cls, res_dict):
        for ks in ("sold_energy", "bought_energy"):
            res_dict[ks + "_lists"] = dict((ki, {}) for ki in res_dict[ks].keys())
            for node in res_dict[ks].keys():
                res_dict[ks + "_lists"][node]["slot"] = \
                    list(res_dict[ks][node]["accumulated"].keys())
                res_dict[ks + "_lists"][node]["energy"] = \
                    list(res_dict[ks][node]["accumulated"].values())

    def _calculate_devices_sold_bought_energy_past_markets(self, area, past_markets):
        out_dict = {"sold_energy": {}, "bought_energy": {}}
        for market in past_markets:
            for trade in market.trades:
                trade_seller = trade.seller[4:] if trade.seller.startswith("IAA ") \
                    else trade.seller
                trade_buyer = trade.buyer[4:] if trade.buyer.startswith("IAA ") \
                    else trade.buyer

                if trade_seller not in out_dict["sold_energy"]:
                    out_dict["sold_energy"][trade_seller] = {}
                    out_dict["sold_energy"][trade_seller]["accumulated"] = dict(
                        (m.time_slot, 0) for m in area.past_markets)
                if trade_buyer not in out_dict["sold_energy"][trade_seller]:
                    out_dict["sold_energy"][trade_seller][trade_buyer] = dict(
                        (m.time_slot, 0) for m in area.past_markets)
                if trade.offer.energy > FLOATING_POINT_TOLERANCE:
                    out_dict["sold_energy"][trade_seller]["accumulated"][market.time_slot] += \
                        trade.offer.energy
                    out_dict["sold_energy"][trade_seller][trade_buyer][market.time_slot] += \
                        trade.offer.energy

                if trade_buyer not in out_dict["bought_energy"]:
                    out_dict["bought_energy"][trade_buyer] = {}
                    out_dict["bought_energy"][trade_buyer]["accumulated"] = dict(
                        (m.time_slot, 0) for m in area.past_markets)
                if trade_seller not in out_dict["bought_energy"][trade_buyer]:
                    out_dict["bought_energy"][trade_buyer][trade_seller] = dict(
                        (m.time_slot, 0) for m in area.past_markets)
                if trade.offer.energy > FLOATING_POINT_TOLERANCE:
                    out_dict["bought_energy"][trade_buyer]["accumulated"][market.time_slot] += \
                        trade.offer.energy
                    out_dict["bought_energy"][trade_buyer][trade_seller][market.time_slot] += \
                        trade.offer.energy
        self._add_sold_bought_lists(out_dict)

        return out_dict

    def _get_buyer_seller_trades(self, area: Area):
        """
        Determines the buy and sell rate of each leaf node
        """
        labels = ("slot", "rate [ct./kWh]", "energy [kWh]", "seller")
        for market in area.past_markets:
            for trade in market.trades:
                buyer_slug = slugify(trade.buyer, to_lower=True)
                seller_slug = slugify(trade.seller, to_lower=True)
                if buyer_slug not in self.buyer_trades:
                    self.buyer_trades[buyer_slug] = dict((key, []) for key in labels)
                if seller_slug not in self.seller_trades:
                    self.seller_trades[seller_slug] = dict((key, []) for key in labels)
                else:
                    values = (market.time_slot,) + \
                             (round(trade.offer.price / trade.offer.energy, 4),
                              (trade.offer.energy * -1),) + \
                             (slugify(trade.seller, to_lower=True),)
                    for ii, ri in enumerate(labels):
                        self.buyer_trades[buyer_slug][ri].append(values[ii])
                        self.seller_trades[seller_slug][ri].append(values[ii])


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
            desired = self.area.strategy.state.desired_energy_Wh[slot] / 1000
            return [desired, self._traded(market) + desired]
        elif isinstance(self.area.strategy, PVStrategy):
            produced = market.actual_energy_agg.get(self.area.name, 0)
            return [produced,
                    round(produced - self.area.strategy.energy_production_forecast_kWh[slot], 4),
                    self.area.strategy.energy_production_forecast_kWh[slot]
                    ]
        return []


class KPI:
    def __init__(self):
        self.performance_index = dict()
        self._cep_device = list()
        self._cep_energy = 0
        self._total_energy = 0

    def __repr__(self):
        return f"KPI: {self.performance_index}"

    def _accumulated_trade_energy(self, area):
        for child in area.children:
            if isinstance(child.strategy, (CommercialStrategy, FinitePowerPlant)):
                self._cep_device.append(child.name)
                self._accumulate_energy(area, child, True)
            elif _is_load_node(child) or _is_prosumer_node(child):
                self._accumulate_energy(area, child, False)

    def _accumulate_energy(self, area, child, is_cep: bool):
        for markets in area.past_markets:
            for trade in markets.trades:
                if is_cep:
                    if trade.offer.seller not in self._cep_device:
                        continue
                    self._cep_energy += trade.offer.energy
                else:
                    if trade.buyer is child.name:
                        self._total_energy += trade.offer.energy

    def _export_house_pv_self_consumption(self, area):
        house_pv_device = list()
        house_load_device = list()
        trade_by_pv = 0
        total_energy_bought = 0
        traded_from_pv = 0
        if not _is_house_node(area):
            return
        for child in area.children:
            if isinstance(child.strategy, PVStrategy):
                house_pv_device.append(child.name)
            elif _is_load_node(child) or _is_prosumer_node(child):
                house_load_device.append(child.name)

        for markets in area.past_markets:
            for trade in markets.trades:
                # Total Electricity traded by house device
                if trade.buyer in house_load_device:
                    total_energy_bought += trade.offer.energy
                # Electricity produced by PV
                if trade.offer.seller in house_pv_device:
                    trade_by_pv += trade.offer.energy
                # PV electricity self_consumption
                if trade.offer.seller in house_pv_device and trade.buyer in house_load_device:
                    traded_from_pv += trade.offer.energy

        if trade_by_pv != 0:
            self_consumption_within_house = traded_from_pv / trade_by_pv
        else:
            self_consumption_within_house = 0
        if total_energy_bought != 0:
            self_sufficiency = traded_from_pv / total_energy_bought
        else:
            self_sufficiency = 0

        return {"self_consumption_within_house": self_consumption_within_house,
                "self_sufficiency": self_sufficiency}

    def update_kpis_from_area(self, area):
        self._accumulated_trade_energy(area)
        self.performance_index[area.name] = \
            self._export_house_pv_self_consumption(area)
        if self._total_energy is not 0:
            cep_share = self._cep_energy / self._total_energy
        else:
            cep_share = 0
        self.performance_index["global-non-renewable-energy-share"] = cep_share
