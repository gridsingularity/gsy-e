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
from pendulum import duration
from itertools import product

from d3a.models.strategy.load_hours import LoadHoursStrategy
from d3a.models.const import GlobalConfig
from d3a.constants import DATE_TIME_FORMAT, FLOATING_POINT_TOLERANCE

DATE_HOUR_FORMAT = "YYYY-MM-DDTHH"


def get_number_of_unmatched_loads(indict):
    # use root dict:
    root = indict[list(indict.keys())[0]]
    no_ul = 0
    for parent in root.values():
        for value in parent.values():
            no_ul += value['unmatched_count']
    return no_ul


def hour_list():
    if GlobalConfig.sim_duration > duration(days=1):
        return [GlobalConfig.start_date.add(days=day, hours=hour)
                for day, hour in product(range(GlobalConfig.sim_duration.days), range(24))]
    else:
        return [GlobalConfig.start_date.add(hours=hour) for hour in range(24)]


class ExportUnmatchedLoads:
    def __init__(self, area):

        self.hour_list = hour_list()
        # This is for only returning data until the current time_slot:
        if hasattr(area, "past_markets") and len(list(area.past_markets)) > 0:
            self.latest_time_slot = list(area.past_markets)[-1].time_slot
        else:
            self.latest_time_slot = self.hour_list[0]
        self.name_uuid_map = {area.name: area.uuid}
        self.area = area

    def __call__(self):

        unmatched_loads = self.arrange_output(
            self.expand_to_ul_to_hours(
                self.expand_ul_to_parents(
                    self.find_unmatched_loads(self.area, {})[self.area.name],
                    self.area.name, {})),
            self.area)

        return unmatched_loads, self.change_name_to_uuid(unmatched_loads)

    def find_unmatched_loads(self, area, indict):
        """
        Aggregates list of times for each unmatched time slot for each load
        """
        indict[area.name] = {}
        for child in area.children:
            self.name_uuid_map[child.name] = child.uuid
            if child.children:
                indict[area.name] = self.find_unmatched_loads(child, indict[area.name])
            else:
                if isinstance(child.strategy, LoadHoursStrategy):
                    indict[area.name][child.name] = \
                        self._calculate_unmatched_loads_leaf_area(child)
        return indict

    @classmethod
    def _calculate_unmatched_loads_leaf_area(cls, area):
        """
        actually determines the unmatched loads
        """
        unmatched_times = []
        for market in area.parent.past_markets:
            desired_energy_Wh = area.strategy.state.desired_energy_Wh[market.time_slot]
            traded_energy_kWh = market.traded_energy[area.name] \
                if market is not None and (area.name in market.traded_energy) \
                else 0.0
            deficit = desired_energy_Wh + traded_energy_kWh * 1000.0
            if deficit > FLOATING_POINT_TOLERANCE:
                unmatched_times.append(market.time_slot)
        return {"unmatched_times": unmatched_times}

    def change_name_to_uuid(self, indict):
        """
        postprocessing: changing area names to uuids
        """
        new = {}
        for k, v in indict.items():
            new[self.name_uuid_map[k]] = v
        return new

    def _accumulate_all_uls_in_branch(self, subdict, unmatched_list) -> list:
        """
        aggregate all unmatched loads times in one branch into one list
        """
        for key in subdict.keys():
            if key == "unmatched_times":
                return unmatched_list + subdict[key]
            else:
                unmatched_list = self._accumulate_all_uls_in_branch(subdict[key], unmatched_list)
        return unmatched_list

    def expand_ul_to_parents(self, subdict, parent_name, outdict):
        """
        expand unmatched loads times to all nodes including all unmatched loads times of the
        sub branch
        """

        for node_name, subsubdict in subdict.items():
            if isinstance(subsubdict, dict):
                # nodes
                ul_list = self._accumulate_all_uls_in_branch(subsubdict, [])
                sub_ul = sorted(list(set(ul_list)))
                if parent_name in outdict:
                    outdict[parent_name].update({node_name: sub_ul})
                else:
                    outdict[parent_name] = {node_name: sub_ul}
                outdict.update(self.expand_ul_to_parents(subsubdict, node_name, {}))
            else:
                # leafs
                outdict[parent_name] = {parent_name: subsubdict}

        return outdict

    @classmethod
    def _get_hover_info(cls, indict, hour_time):
        """
        returns dict of UL for each subarea for the hover the UL graph
        """
        hover_dict = {}
        ul_count = 0
        for child_name, child_ul_list in indict.items():
            for time in child_ul_list:
                if time.hour == hour_time.hour and \
                   time.day == hour_time.day and \
                   time.month == hour_time.month and \
                   time.year == hour_time.year:
                    ul_count += 1
                    if child_name in hover_dict:
                        hover_dict[child_name].append(time.format(DATE_TIME_FORMAT))
                    else:
                        hover_dict[child_name] = [time.format(DATE_TIME_FORMAT)]
        if hover_dict == {}:
            return {"unmatched_count": 0}
        else:
            return {"unmatched_count": ul_count, "unmatched_times": hover_dict}

    def expand_to_ul_to_hours(self, indict):
        """
        Changing format to dict of hour time stamps
        """
        outdict = {}
        for node_name, subdict in indict.items():
            outdict[node_name] = {}
            for hour_time in self.hour_list:
                if hour_time <= self.latest_time_slot:
                    outdict[node_name][hour_time.format(DATE_HOUR_FORMAT)] = \
                        self._get_hover_info(subdict, hour_time)
        return outdict

    def arrange_output(self, indict, area):
        if area.children:
            indict[area.name] = {}
            for child in area.children:
                if child.children or isinstance(child.strategy, LoadHoursStrategy):
                    if child.name in indict:
                        indict[area.name][child.name] = indict[child.name]
                    self.arrange_output(indict, child)
        return indict
