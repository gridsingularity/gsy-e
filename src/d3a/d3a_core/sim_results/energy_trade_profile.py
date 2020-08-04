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
from d3a.constants import FLOATING_POINT_TOLERANCE
from d3a.d3a_core.util import generate_market_slot_list, round_floats_for_ui, \
    area_name_from_area_or_iaa_name
from d3a_interface.constants_limits import ConstSettings
from d3a_interface.sim_results.aggregate_results import merge_energy_trade_profile_to_global
from d3a.d3a_core.util import add_or_create_key

trade_profile_init_dict = {"sold_energy": {}, "bought_energy": {}}


class EnergyTradeProfile:
    def __init__(self, should_export_plots):
        self.traded_energy_profile = {}
        self.traded_energy_current = {}
        self.balancing_traded_energy = {}
        self.time_slots = []
        self.should_export_plots = should_export_plots

    def update(self, area):
        if len(self.time_slots) == 0:
            self.time_slots = generate_market_slot_list(area)
        self.traded_energy_current = {}
        self._populate_area_children_data(area)

    def _populate_area_children_data(self, area):
        if area.children:
            for child in area.children:
                self._populate_area_children_data(child)
            if self.should_export_plots:
                self.update_sold_bought_energy(area)
            else:
                self.update_current_energy_trade_profile(area)

    def update_current_energy_trade_profile(self, area):
        if area.current_market is not None:
            self.traded_energy_current[area.uuid] = trade_profile_init_dict
            self.calculate_devices_sold_bought_energy(self.traded_energy_current[area.uuid],
                                                      area.current_market,
                                                      [area.current_market.time_slot])
            self.round_energy_trade_profile(self.traded_energy_current)

    def update_sold_bought_energy(self, area: Area):
        if area.current_market is not None:
            if area.name not in self.traded_energy_current:
                self.traded_energy_current[area.name] = trade_profile_init_dict

            self.calculate_devices_sold_bought_energy(
                self.traded_energy_current[area.name],
                area.current_market, [area.current_market.time_slot])

            traded_energy_current_name = {area.name: self.traded_energy_current[area.name]}
            self.traded_energy_profile = merge_energy_trade_profile_to_global(
                traded_energy_current_name, self.traded_energy_profile,
                self.time_slots)
            if ConstSettings.BalancingSettings.ENABLE_BALANCING_MARKET:
                # balancing energy
                if area.name not in self.balancing_traded_energy:
                    self.balancing_traded_energy[area.name] = trade_profile_init_dict
                if len(area.past_balancing_markets) > 0:
                    self.calculate_devices_sold_bought_energy(
                        self.balancing_traded_energy[area.name], area.current_balancing_market,
                        self.time_slots)

    @staticmethod
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
                add_or_create_key(res_dict["bought_energy"][trade_buyer]["accumulated"],
                                  market.time_slot, trade.offer.energy)
                add_or_create_key(res_dict["bought_energy"][trade_buyer][trade_seller],
                                  market.time_slot, trade.offer.energy)

    @staticmethod
    def round_energy_trade_profile(profile):
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

    @staticmethod
    def add_sold_bought_lists(res_dict):
        for area_name in res_dict.keys():
            for ks in ("sold_energy", "bought_energy"):
                res_dict[area_name][ks + "_lists"] = \
                    dict((ki, {}) for ki in res_dict[area_name][ks].keys())
                for node in res_dict[area_name][ks].keys():
                    res_dict[area_name][ks + "_lists"][node]["slot"] = \
                        list(res_dict[area_name][ks][node]["accumulated"].keys())
                    res_dict[area_name][ks + "_lists"][node]["energy"] = \
                        list(res_dict[area_name][ks][node]["accumulated"].values())
