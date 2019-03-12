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
from d3a.constants import FLOATING_POINT_TOLERANCE
from functools import reduce
import operator


def get_from_dict(data_dict, map_list):
    return reduce(operator.getitem, map_list, data_dict)


def set_in_dict(data_dict, map_list, value):
    get_from_dict(data_dict, map_list[:-1])[map_list[-1]] = value


UNMACHTED_STATS_KEYS = ["unmatched_areas", "unmatched_hours", "unmatched_load_count"]


class ExportUnmatchedLoads:
    def __init__(self, area):
        self.leaf_address_list = {}
        self.uuid_dict = {area.name: area.uuid}
        self.unmatched_loads_redis = {}

        self.unmatched_loads = self.find_unmatched_loads(area, {})
        self.find_unmatched_leafs(self.unmatched_loads, [])
        self.update_ul_to_parents()
        self.modify_for_redis(self.unmatched_loads)

    def find_unmatched_loads(self, area, indict):
        indict[area.name] = {}
        for child in area.children:
            self.uuid_dict[child.name] = child.uuid
            if child.children:
                indict[area.name] = self.find_unmatched_loads(child, indict[area.name])
            else:
                if isinstance(child.strategy, LoadHoursStrategy):
                    indict[area.name][child.name] = self.accumulate_unmatched_load(child)
        return indict

    @classmethod
    def accumulate_unmatched_load(cls, area):
        unmatched_times = []
        for market in area.parent.past_markets:
            desired_energy_Wh = area.strategy.state.desired_energy_Wh[market.time_slot]
            traded_energy_kWh = market.traded_energy[area.name] \
                if market is not None and (area.name in market.traded_energy) \
                else 0.0
            deficit = desired_energy_Wh + traded_energy_kWh * 1000.0
            if deficit > FLOATING_POINT_TOLERANCE:
                unmatched_times.append(market.time_slot_str)
        return {"unmatched_hours": unmatched_times,
                "unmatched_load_count": len(unmatched_times),
                "unmatched_areas": [area.name]}

    def find_unmatched_leafs(self, indict, address):
        for child_key in indict.keys():
            if isinstance(indict[child_key], dict):
                if "unmatched_load_count" in indict[child_key].keys():
                    self.leaf_address_list[child_key] = address
                else:
                    new_address = address + [child_key]
                    self.find_unmatched_leafs(indict[child_key], new_address)

    def update_ul_to_parents(self):
        for leaf_name, address_list in self.leaf_address_list.items():
            leaf_address = address_list + [leaf_name]
            leaf_dict = get_from_dict(self.unmatched_loads, leaf_address)
            for ii in reversed(range(1, len(address_list)+1)):
                parent_address = address_list[0:ii]
                if ii == len(address_list):
                    ul_name = leaf_name
                else:
                    ul_name = address_list[ii]

                updated_dict = self.copy_ul_to_parent(leaf_dict,
                                                      get_from_dict(self.unmatched_loads,
                                                                    parent_address), ul_name)
                set_in_dict(self.unmatched_loads, parent_address, updated_dict)

    @classmethod
    def copy_ul_to_parent(cls, child_dict, parent_dict, child_key):
        if "unmatched_areas" in parent_dict.keys():
            parent_dict["unmatched_areas"] = list(set(parent_dict["unmatched_areas"]
                                                      + [child_key]))
            parent_dict["unmatched_hours"] = sorted(list(set(parent_dict["unmatched_hours"]
                                                             + child_dict["unmatched_hours"])))
            parent_dict["unmatched_load_count"] = len(parent_dict["unmatched_hours"])
        else:
            parent_dict["unmatched_areas"] = [child_key]
            parent_dict["unmatched_hours"] = child_dict["unmatched_hours"]
            parent_dict["unmatched_load_count"] = len(parent_dict["unmatched_hours"])
        return parent_dict

    def modify_for_redis(self, subdict):
        for key in subdict.keys():
            if isinstance(subdict[key], dict) and key in self.uuid_dict:
                stats_dict = dict((stats_key, subdict[key][stats_key])
                                  for stats_key in UNMACHTED_STATS_KEYS)
                self.unmatched_loads_redis.update({self.uuid_dict[key]: stats_dict})
                self.modify_for_redis(subdict[key])
