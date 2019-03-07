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


class ExportUnmatchedLoads:
    def __init__(self, area):
        # self.unmatched_loads = {}

        self.unmatched_loads_temp = self.find_unmatched_loads(area, {}, "")
        self.unmatched_loads = self.update_to_parents(self.unmatched_loads_temp)
        # self.unmatched_loads = self.find_loads_build_tree(area, {})

        # self.unmatched_loads = self.accumulate_unmatched_loads({"children":
        #  self.unmatched_loads})

    def find_unmatched_loads(self, area, indict, parent):
        indict[area.name] = {}
        for child in area.children:
            if child.children:
                indict[area.name] = self.find_unmatched_loads(child, indict[area.name], area.name)
            else:
                if isinstance(child.strategy, LoadHoursStrategy):
                    indict[area.name][child.name] = self.accumulate_unmatched_load(child)
                    indict[area.name][child.name]["parent"] = area.name
                    # if indict[area.name][child.name]["unmatched_load_count"] > 0:
                    #     indict[area.name].update(self.copy_ul_to_parent(
                    # indict[area.name][child.name], indict[area.name], child.name))
        if parent != "":
            indict[area.name]["parent"] = parent
        return indict

    def accumulate_unmatched_load(self, area):
        unmatched_times = []
        for market in area.parent.past_markets:
            desired_energy_Wh = area.strategy.state.desired_energy_Wh[market.time_slot]
            traded_energy_kWh = market.traded_energy[area.name] \
                if market is not None and (area.name in market.traded_energy) \
                else 0.0
            deficit = desired_energy_Wh + traded_energy_kWh * 1000.0
            if deficit > FLOATING_POINT_TOLERANCE:
                unmatched_times.append(market.time_slot_str)
        return {"unmatched_loads": unmatched_times, "unmatched_load_count": len(unmatched_times)}

    def update_to_parents(self, parent_dict):
        for child_key in parent_dict.keys():
            if isinstance(parent_dict[child_key], dict):
                if "unmatched_load_count" in parent_dict[child_key].keys():
                    if parent_dict[child_key]["unmatched_load_count"] > 0:
                        parent_dict = self.copy_ul_to_parent(parent_dict[child_key],
                                                             parent_dict, child_key)
                else:
                    return self.update_to_parents(parent_dict[child_key])

    def copy_ul_to_parent(self, copy_dict, parent_dict, child_key):
        if "loads" in parent_dict.keys():
            parent_dict["loads"].append(child_key)
            parent_dict["unmatched_loads"] = set(parent_dict["unmatched_loads"]
                                                 + copy_dict["unmatched_loads"])
        else:
            parent_dict["loads"] = [child_key]
            parent_dict["unmatched_loads"] = copy_dict["unmatched_loads"]

        return parent_dict

    #
    #     else:
    #         print("häääää")
    #         return indict
    #
    #
    #
    # def find_loads_build_tree(self, area, indict):
    #     if not area.children:
    #         if not isinstance(area.strategy, LoadHoursStrategy):
    #             return indict
    #
    #     indict[area.name] = {"unmatched_load_count": 0,  "children": {}}
    #
    #     indict[area.name].update(self._calculate_area_stats(area))
    #     for child in area.children:
    #         indict[area.name]["children"] = self.find_loads_build_tree(child,
    #  indict[area.name]["children"])
    #
    #     return indict
    #
    #
    # def _calculate_hour_stats_for_area(self, hour_data, area, current_slot):
    #     if area.children == []:
    #         return self._calculate_stats_for_single_device(hour_data, area, current_slot)
    #     else:
    #         for child in area.children:
    #             hour_data = self._calculate_stats_for_single_device(hour_data, child,
    # current_slot)
    #         return hour_data
    #
    # def _calculate_area_stats(self, area):
    #     if not area.parent:
    #         return {}
    #     per_hour_device_data = {}
    #     # Iterate first through all the available market slots of the area
    #     for market in area.parent.past_markets:
    #         current_slot = market.time_slot
    #         hour_data = per_hour_device_data.get(current_slot.hour, {"devices": {}})
    #         # Update hour data for the area, by accumulating slots in one hour
    #         per_hour_device_data[current_slot.hour] = \
    #             self._calculate_hour_stats_for_area(hour_data, area, current_slot)
    #     area_data = self._accumulate_device_stats_to_area_stats(per_hour_device_data)
    #     # area_data["type"] = get_area_type_string(area)
    #     return area_data
    #
    # def _accumulate_device_stats_to_area_stats(self, per_hour_device_data):
    #     for hour, unmatched_loads in per_hour_device_data.items():
    #         # this table holds the unmatched_count/timepoints dictionary
    #         # for all the devices of this hour.
    #         device_data_list = unmatched_loads["devices"].values()
    #         per_hour_device_data[hour]["unmatched_load_count"] = \
    #             sum([v["unmatched_load_count"] for v in device_data_list])
    #         per_hour_device_data[hour]["all_loads_met"] = \
    #             (per_hour_device_data[hour]["unmatched_load_count"] == 0)
    #         # For the UI's convenience, devices should be presented as arrays
    #         per_hour_device_data[hour]["devices"] = [per_hour_device_data[hour]["devices"]]
    #     area_data = {
    #         "timeslots": per_hour_device_data,
    #         "unmatched_load_count": sum([data["unmatched_load_count"]
    #                                      for _, data in per_hour_device_data.items()])
    #     }
    #     area_data["all_loads_met"] = (area_data["unmatched_load_count"] == 0)
    #     return area_data
    #
    # def _calculate_stats_for_single_device(self, hour_data, area, current_slot):
    #     if isinstance(area.strategy, (LoadHoursStrategy, DefinedLoadStrategy)):
    #         desired_energy_Wh = area.strategy.state.desired_energy_Wh[current_slot]
    #     else:
    #         return hour_data
    #     selected_market = area.parent.get_past_market(current_slot)
    #     traded_energy_kWh = selected_market.traded_energy[area.name] \
    #         if selected_market is not None and (area.name in selected_market.traded_energy) \
    #         else 0.0
    #     # Different sign conventions, hence the +
    #     deficit = desired_energy_Wh + traded_energy_kWh * 1000.0
    #     if deficit > FLOATING_POINT_TOLERANCE:
    #         # Get the hour data entry for this hour, or create an empty one if not there
    #         device = hour_data["devices"].get(
    #             area.slug,
    #             {"unmatched_load_count": 0, "timepoints": []}
    #         )
    #         # Update load hour entry
    #         device["unmatched_load_count"] += 1
    #         device["timepoints"].append(current_slot.to_time_string())
    #         hour_data["devices"][area.slug] = device
    #     return hour_data
