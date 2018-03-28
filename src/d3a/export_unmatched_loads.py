from d3a.models.strategy.load_hours_fb import LoadHoursStrategy
from d3a.models.strategy.permanent import PermanentLoadStrategy
from logging import getLogger

log = getLogger(__name__)


DEFICIT_THRESHOLD_Wh = 0.001


def _calculate_hour_stats_for_devices(hour_data, area, current_slot):
    for child in area.children:
        if isinstance(child.strategy, LoadHoursStrategy):
            desired_energy = child.strategy.state.desired_energy[current_slot]
        elif isinstance(child.strategy, PermanentLoadStrategy):
            desired_energy = child.strategy.energy
        else:
            continue
        traded_energy = \
            child.past_markets[current_slot].traded_energy[child.name] \
            if (current_slot in child.past_markets) and \
               (child.name in child.past_markets[current_slot].traded_energy) \
            else 0.0
        deficit = desired_energy - traded_energy
        if deficit > DEFICIT_THRESHOLD_Wh:
            # Get the hour data entry for this hour, or create an empty one if not there
            device = hour_data["devices"].get(
                child.slug,
                {"unmatched_load_count": 0, "timepoints": []}
            )
            # Update load hour entry
            device["unmatched_load_count"] += 1
            device["timepoints"].append(current_slot.to_time_string())
            hour_data["devices"][child.slug] = device
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


def _calculate_house_area_stats(area):
    per_hour_device_data = {}
    # Iterate first through all the available market slots of the area
    for current_slot, market in area.past_markets.items():
        hour_data = per_hour_device_data.get(current_slot.hour, {"devices": {}})
        # Update hour data for the area, by accumulating slots in one hour
        per_hour_device_data[current_slot.hour] = \
            _calculate_hour_stats_for_devices(hour_data, area, current_slot)
    return _accumulate_device_stats_to_area_stats(per_hour_device_data)


def _recurse_area_tree(area):
    unmatched_loads = {}
    for child in area.children:
        if child.children is None:
            # We are at a leaf node, no point in recursing further. This node's calculation
            # should be done on the upper level
            continue
        elif all(grandkid.children == [] for grandkid in child.children) and \
                (any(isinstance(grandkid.strategy, LoadHoursStrategy) or
                     isinstance(grandkid.strategy, PermanentLoadStrategy)
                     for grandkid in child.children)):
            # House level: validate that all grandkids are leaves, and there is
            # at least one load included amongst children
            unmatched_loads[child.slug] = _calculate_house_area_stats(child)
        else:
            # Recurse even further. Merge new results with existing ones
            unmatched_loads = {**unmatched_loads, **_recurse_area_tree(child)}
    return unmatched_loads


def export_unmatched_loads(area):
    unmatched_loads_result = {}
    area_tree = _recurse_area_tree(area)
    # Calculate overall metrics for the whole grid
    unmatched_loads_result["unmatched_load_count"] = \
        sum([v["unmatched_load_count"] for k, v in area_tree.items()])
    unmatched_loads_result["all_loads_met"] = (unmatched_loads_result["unmatched_load_count"] == 0)
    unmatched_loads_result["areas"] = area_tree
    return unmatched_loads_result
