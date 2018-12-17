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
from collections import OrderedDict

from d3a.models.strategy.load_hours import LoadHoursStrategy, CellTowerLoadHoursStrategy
from d3a.models.strategy.predefined_load import DefinedLoadStrategy
from d3a.d3a_core.sim_results.area_statistics import get_area_type_string


DEFICIT_THRESHOLD_Wh = 0.0001


def _calculate_stats_for_single_device(hour_data, area, current_slot):
    if isinstance(area.strategy, (LoadHoursStrategy, DefinedLoadStrategy)):
        desired_energy_Wh = area.strategy.state.desired_energy_Wh[current_slot]
    else:
        return hour_data
    selected_market = area.parent.get_past_market(current_slot)
    traded_energy_kWh = selected_market.traded_energy[area.name] \
        if selected_market is not None and (area.name in selected_market.traded_energy) \
        else 0.0
    # Different sign conventions, hence the +
    deficit = desired_energy_Wh + traded_energy_kWh * 1000.0
    if deficit > DEFICIT_THRESHOLD_Wh:
        # Get the hour data entry for this hour, or create an empty one if not there
        device = hour_data["devices"].get(
            area.slug,
            {"unmatched_load_count": 0, "timepoints": []}
        )
        # Update load hour entry
        device["unmatched_load_count"] += 1
        device["timepoints"].append(current_slot.to_time_string())
        hour_data["devices"][area.slug] = device
    return hour_data


def _calculate_hour_stats_for_area(hour_data, area, current_slot):
    if area.children == []:
        return _calculate_stats_for_single_device(hour_data, area, current_slot)
    else:
        for child in area.children:
            hour_data = _calculate_stats_for_single_device(hour_data, child, current_slot)
        return hour_data


def _accumulate_device_stats_to_area_stats(per_hour_device_data):
    for hour, unmatched_loads in per_hour_device_data.items():
        # this table holds the unmatched_count/timepoints dictionary
        # for all the devices of this hour.
        device_data_list = unmatched_loads["devices"].values()
        per_hour_device_data[hour]["unmatched_load_count"] = \
            sum([v["unmatched_load_count"] for v in device_data_list])
        per_hour_device_data[hour]["all_loads_met"] = \
            (per_hour_device_data[hour]["unmatched_load_count"] == 0)
        # For the UI's convenience, devices should be presented as arrays
        per_hour_device_data[hour]["devices"] = [per_hour_device_data[hour]["devices"]]
    area_data = {
        "timeslots": per_hour_device_data,
        "unmatched_load_count": sum([data["unmatched_load_count"]
                                     for _, data in per_hour_device_data.items()])
    }
    area_data["all_loads_met"] = (area_data["unmatched_load_count"] == 0)
    return area_data


def _calculate_area_stats(area):
    per_hour_device_data = {}
    # Iterate first through all the available market slots of the area
    for market in area.parent.past_markets:
        current_slot = market.time_slot
        hour_data = per_hour_device_data.get(current_slot.hour, {"devices": {}})
        # Update hour data for the area, by accumulating slots in one hour
        per_hour_device_data[current_slot.hour] = \
            _calculate_hour_stats_for_area(hour_data, area, current_slot)
    area_data = _accumulate_device_stats_to_area_stats(per_hour_device_data)
    area_data["type"] = get_area_type_string(area)
    return area_data


def _is_house_node(area):
    # Should not include any houses that do not have loads, therefore the houses are
    # further filtered out to contain at least one load
    return all(grandkid.children == [] for grandkid in area.children) and \
           (any(isinstance(grandkid.strategy, (LoadHoursStrategy, DefinedLoadStrategy))
                for grandkid in area.children))


def _is_cell_tower_node(area):
    return isinstance(area.strategy, CellTowerLoadHoursStrategy)


def _recurse_area_tree(area, area_select_function):
    unmatched_loads = {}
    for child in area.children:
        if area_select_function(child):
            # Need to iterate, because the area has been marked as a house or cell tower
            unmatched_loads[child.name] = _calculate_area_stats(child)
        elif child.children is None:
            # We are at a leaf node, no point in recursing further. This node's calculation
            # should be done on the upper level
            continue
        else:
            # Recurse even further. Merge new results with existing ones
            unmatched_loads = {**unmatched_loads,
                               **_recurse_area_tree(child, area_select_function)}
    return unmatched_loads


def select_house_or_cell_tower(area):
    return _is_house_node(area) or _is_cell_tower_node(area)


def select_house_or_load(area):
    return _is_house_node(area) or isinstance(area.strategy, LoadHoursStrategy)


def export_unmatched_loads(area, all_devices=False):
    unmatched_loads_result = {}

    area_select_function = select_house_or_load if all_devices else select_house_or_cell_tower
    area_tree = _recurse_area_tree(area, area_select_function)
    # Calculate overall metrics for the whole grid
    unmatched_loads_result["unmatched_load_count"] = \
        sum([v["unmatched_load_count"] for k, v in area_tree.items()])
    unmatched_loads_result["all_loads_met"] = (unmatched_loads_result["unmatched_load_count"] == 0)
    area_tree = OrderedDict(sorted(area_tree.items()))
    unmatched_loads_result["areas"] = area_tree
    return unmatched_loads_result
