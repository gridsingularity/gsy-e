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
from d3a.constants import FLOATING_POINT_TOLERANCE
from d3a.d3a_core.util import round_floats_for_ui, area_name_from_area_or_iaa_name
from d3a_interface.sim_results.aggregate_results import merge_energy_trade_profile_to_global
from d3a.d3a_core.util import add_or_create_key
from d3a_interface.utils import key_in_dict_and_not_none, ui_str_to_pendulum_datetime


class EnergyTradeProfile:
    def __init__(self, should_export_plots):
        self.traded_energy_profile = {}
        self.traded_energy_current = {}
        self.should_export_plots = should_export_plots

    def update(self, area_result_dict=None, core_stats=None, current_market_slot=None):
        self.traded_energy_current = {}
        self._populate_area_children_data(area_result_dict, core_stats, current_market_slot)

    def _populate_area_children_data(self, area_result_dict, core_stats, current_market_slot):
        if key_in_dict_and_not_none(area_result_dict, 'children'):
            for child in area_result_dict["children"]:
                self._populate_area_children_data(child, core_stats, current_market_slot)
            if self.should_export_plots:
                self.update_sold_bought_energy(area_result_dict, core_stats, current_market_slot)
            else:
                self.update_current_energy_trade_profile(
                    area_result_dict, core_stats, current_market_slot
                )

    def update_current_energy_trade_profile(self, area_result_dict, core_stats,
                                            current_market_slot):
        if current_market_slot is not None:
            self.traded_energy_current[area_result_dict["uuid"]] = {
                "sold_energy": {}, "bought_energy": {}
            }
            self.calculate_devices_sold_bought_energy(
                self.traded_energy_current[area_result_dict["uuid"]],
                area_result_dict,
                core_stats,
                current_market_slot
            )
            self.round_energy_trade_profile(self.traded_energy_current)

    def update_sold_bought_energy(self, area_result_dict, core_stats, current_market_slot):
        if current_market_slot is not None:
            area_name = area_result_dict["name"]
            self.traded_energy_current[area_name] = {"sold_energy": {}, "bought_energy": {}}
            self.calculate_devices_sold_bought_energy(
                self.traded_energy_current[area_name], area_result_dict,
                core_stats, current_market_slot)

            traded_energy_current_name = {area_name: self.traded_energy_current[area_name]}
            self.traded_energy_profile = merge_energy_trade_profile_to_global(
                traded_energy_current_name, self.traded_energy_profile,
                [current_market_slot])

    @staticmethod
    def calculate_devices_sold_bought_energy(res_dict, area_result_dict, core_stats,
                                             current_market_slot):
        if area_result_dict['uuid'] not in core_stats:
            return
        if core_stats[area_result_dict['uuid']] == {}:
            return
        area_core_trades = core_stats[area_result_dict['uuid']].get('trades', [])
        for trade in area_core_trades:
            trade_seller = area_name_from_area_or_iaa_name(trade["seller"])
            trade_buyer = area_name_from_area_or_iaa_name(trade["buyer"])

            if trade_seller not in res_dict["sold_energy"]:
                res_dict["sold_energy"][trade_seller] = {"accumulated": {}}
            if trade_buyer not in res_dict["sold_energy"][trade_seller]:
                res_dict["sold_energy"][trade_seller][trade_buyer] = {}
            trade_energy = trade["energy"]
            if trade_energy > FLOATING_POINT_TOLERANCE:
                add_or_create_key(res_dict["sold_energy"][trade_seller]["accumulated"],
                                  current_market_slot, trade_energy)
                add_or_create_key(res_dict["sold_energy"][trade_seller][trade_buyer],
                                  current_market_slot, trade_energy)
            if trade_buyer not in res_dict["bought_energy"]:
                res_dict["bought_energy"][trade_buyer] = {"accumulated": {}}
            if trade_seller not in res_dict["bought_energy"][trade_buyer]:
                res_dict["bought_energy"][trade_buyer][trade_seller] = {}
            if trade_energy > FLOATING_POINT_TOLERANCE:
                add_or_create_key(res_dict["bought_energy"][trade_buyer]["accumulated"],
                                  current_market_slot, trade_energy)
                add_or_create_key(res_dict["bought_energy"][trade_buyer][trade_seller],
                                  current_market_slot, trade_energy)

    @staticmethod
    def round_energy_trade_profile(profile):
        for k in profile.keys():
            for sold_bought in ("sold_energy", "bought_energy"):
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

    @staticmethod
    def convert_timestamp_strings_to_datetimes(profile):
        outdict = {}
        for k in profile.keys():
            outdict[k] = {}
            for sold_bought in ("sold_energy", "bought_energy"):
                if sold_bought not in profile[k]:
                    continue
                outdict[k][sold_bought] = {}
                for dev in profile[k][sold_bought].keys():
                    outdict[k][sold_bought][dev] = {}
                    for target in profile[k][sold_bought][dev].keys():
                        outdict[k][sold_bought][dev][target] = {}
                        for timestamp_str in profile[k][sold_bought][dev][target].keys():
                            datetime_obj = ui_str_to_pendulum_datetime(timestamp_str)
                            outdict[k][sold_bought][dev][target][datetime_obj] = \
                                profile[k][sold_bought][dev][target][timestamp_str]
        return outdict
