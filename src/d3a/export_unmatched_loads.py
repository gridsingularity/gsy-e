from d3a.models.strategy.load_hours_fb import LoadHoursStrategy
from d3a.models.strategy.permanent import PermanentLoadStrategy
from logging import getLogger


log = getLogger(__name__)


def get_unmatched_loads_from_house_area(area):
    area_data = {}
    current_hourly_data = {}
    # Get the market slots for the area
    for current_slot, market in area.past_markets.items():
        # Add a dictionary entry for the current hour, that will accumulate timeslot data.
        # Add placeholder dictionary for devices.
        if current_slot.hour not in current_hourly_data.keys():
            current_hourly_data[current_slot.hour] = {}
            current_hourly_data[current_slot.hour]["devices"] = {}
        for child in area.children:
            if isinstance(child.strategy, LoadHoursStrategy):
                desired_energy = child.strategy.state.desired_energy[current_slot]
            elif isinstance(child.strategy, PermanentLoadStrategy):
                desired_energy = child.strategy.energy
            else:
                continue
            if child.slug not in current_hourly_data[current_slot.hour]["devices"].keys():
                current_hourly_data[current_slot.hour]["devices"][child.slug] = 0
            traded_energy = child.markets[current_slot].traded_energy[child.name] \
                if current_slot in child.markets else 0.0
            deficit = traded_energy - desired_energy
            if deficit < 0.0:
                current_hourly_data[current_slot.hour]["devices"][child.slug] += 1
    for hour, unmatched_loads in current_hourly_data.items():
        current_hourly_data[hour]["unmatched_load_count"] = \
            sum(list(unmatched_loads["devices"].values()))
        current_hourly_data[hour]["all_loads_met"] = \
            (current_hourly_data[hour]["unmatched_load_count"] == 0)
        current_hourly_data[hour]["devices"] = [current_hourly_data[hour]["devices"]]
        # current_hourly_data[hour]["hour"] = hour
    sorted_hourly_data = sorted(current_hourly_data.items(), key=lambda kv: kv[0])
    area_data["timeslots"] = [timeslot for (_, timeslot) in sorted_hourly_data]
    area_data["unmatched_load_count"] = \
        sum([data["unmatched_load_count"] for _, data in current_hourly_data.items()])
    area_data["all_loads_met"] = (area_data["unmatched_load_count"] == 0)
    return area_data


def export_unmatched_loads(area):
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
            unmatched_loads[child.slug] = get_unmatched_loads_from_house_area(child)
        else:
            # Recurse even further. Merge new results with existing ones
            unmatched_loads = {**unmatched_loads, **export_unmatched_loads(child)}
    return unmatched_loads


def final_export_unmatched_loads(area):
    final_unmatched = export_unmatched_loads(area)
    # Calculate overall metrics for the whole grid
    final_unmatched["unmatched_load_count"] = \
        sum([v["unmatched_load_count"] for k, v in final_unmatched.items()])
    final_unmatched["all_loads_met"] = (final_unmatched["unmatched_load_count"] == 0)
    return final_unmatched
