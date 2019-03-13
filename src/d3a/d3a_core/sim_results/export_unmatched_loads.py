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
from pendulum import duration, from_format
from itertools import product
from d3a.models.const import GlobalConfig
from d3a.constants import TIME_FORMAT, DATE_TIME_FORMAT


DATE_HOUR_FORMAT = "YYYY-MM-DDTHH"


def hour_list():
    if GlobalConfig.sim_duration > duration(days=1):
        return [GlobalConfig.start_date.add(days=day, hours=hour).format(DATE_HOUR_FORMAT)
                for day, hour in product(range(GlobalConfig.sim_duration.days), range(24))]
    else:
        return [GlobalConfig.start_date.add(hours=hour).format(DATE_HOUR_FORMAT)
                for hour in range(24)]


class ExportUnmatchedLoads:
    def __init__(self, area):

        self.name_uuid_map = {area.name: area.uuid}
        self.unmatched_loads = self.find_unmatched_loads(area, {})

        self.unmatched_loads_redis_tmp = {}
        self.unmatched_loads_redis = {}
        self.expand_ul_to_parents(self.unmatched_loads, "")
        self.expand_to_ul_to_hours()
        self.unmatched_loads_redis = self.change_name_to_uuid(self.unmatched_loads_redis)

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
                    indict[area.name][child.name] = self._accumulate_unmatched_loads(child)
        return indict

    @classmethod
    def _accumulate_unmatched_loads(cls, area):
        """
        actually determines the unmatched loads
        TODO: It would be better to list market.time_slot instead of market.time_slot_str
        TODO: But this is bad for the local export
        TODO: (possible solution: return the same structure for redis locally)
        """
        unmatched_times = []
        for market in area.parent.past_markets:
            desired_energy_Wh = area.strategy.state.desired_energy_Wh[market.time_slot]
            traded_energy_kWh = market.traded_energy[area.name] \
                if market is not None and (area.name in market.traded_energy) \
                else 0.0
            deficit = desired_energy_Wh + traded_energy_kWh * 1000.0
            if deficit > FLOATING_POINT_TOLERANCE:
                unmatched_times.append(market.time_slot_str)
        return {"unmatched_times": unmatched_times}

    def change_name_to_uuid(self, indict):
        """
        postprocessing: changing area names to uuids
        TODO: Could be omitted if local export isnt needed to be readable.
        """
        new = {}
        for k, v in indict.items():
            new[self.name_uuid_map[k]] = v
        return new

    def _accumulate_all_uls_in_branch(self, subdict, unmatched_list) -> list:
        """
        aggregate all UL times in one branch into one list
        """
        for key in subdict.keys():
            if key == "unmatched_times":
                return unmatched_list + subdict[key]
            else:
                unmatched_list = self._accumulate_all_uls_in_branch(subdict[key], unmatched_list)
        return unmatched_list

    def expand_ul_to_parents(self, subdict, parent_name):
        """
        expand UL times to all nodes including all UL times of the sub branch
        TODO:  'if parent_name == "":' is only for the root area, is there another way?
        """
        for node_name, subsubdict in subdict.items():
            if parent_name == "":
                self.expand_ul_to_parents(subsubdict, node_name)
            else:
                if isinstance(subsubdict, dict):
                    ul_list = self._accumulate_all_uls_in_branch(subsubdict, [])
                    sub_ul = sorted(list(set(ul_list)))
                    if parent_name in self.unmatched_loads_redis_tmp:
                        self.unmatched_loads_redis_tmp[parent_name].update({node_name: sub_ul})
                    else:
                        self.unmatched_loads_redis_tmp[parent_name] = {node_name: sub_ul}
                    self.expand_ul_to_parents(subsubdict, node_name)

    @classmethod
    def _get_hover_info(cls, indict, hour_str):
        """
        returns dict of UL for each subarea for the hover the UL graph
        TODO: could be handled with list comprehensions as well !?
        """
        hover_dict = {}
        count = 0
        for child_name, child_ul in indict.items():
            for time in child_ul:
                if from_format(time, DATE_TIME_FORMAT).format(DATE_HOUR_FORMAT) == hour_str:
                    count += 1
                    if child_name in hover_dict:
                        hover_dict[child_name].append(time.format(TIME_FORMAT))
                    else:
                        hover_dict[child_name] = [time.format(TIME_FORMAT)]
        if hover_dict == {}:
            return {"unmatched_count": 0}
        else:
            return {"unmatched_count": count, "unmatched_times": hover_dict}

    def expand_to_ul_to_hours(self):
        """
        Changing format to dict of hour time stamps
        TODO: problem: ALWAYS returns the whole list of hours, not until the current market slot
        """
        for node_name, subdict in self.unmatched_loads_redis_tmp.items():
            self.unmatched_loads_redis[node_name] = {}
            for hour_str in hour_list():
                self.unmatched_loads_redis[node_name][hour_str] = \
                    self._get_hover_info(subdict, hour_str)
