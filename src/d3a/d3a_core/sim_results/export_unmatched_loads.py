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
from copy import deepcopy
from d3a.models.strategy.load_hours import LoadHoursStrategy
from d3a_interface.constants_limits import GlobalConfig
from d3a.constants import DATE_TIME_FORMAT, FLOATING_POINT_TOLERANCE

DATE_HOUR_FORMAT = "YYYY-MM-DDTHH"


def get_number_of_unmatched_loads(indict):
    # use root dict:
    root = indict[list(indict.keys())[0]]
    no_ul = 0
    for parent in root.values():
        for value in parent['unmatched_loads'].values():
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
        self.latest_time_slot = None
        self.name_uuid_map = {area.name: area.uuid}
        self.name_type_map = {area.name: area.display_type}
        self.area = area
        self.load_count = 0
        self.count_load_devices_in_setup(self.area)

    def _set_latest_time_slot(self):
        # This is for only returning data until the current time_slot:
        if hasattr(self.area, "past_markets") and len(list(self.area.past_markets)) > 0:
            self.latest_time_slot = list(self.area.past_markets)[-1].time_slot
        else:
            self.latest_time_slot = self.hour_list[0]

    def count_load_devices_in_setup(self, area):
        for child in area.children:
            if isinstance(child.strategy, LoadHoursStrategy):
                self.load_count += 1
            if child.children:
                self.count_load_devices_in_setup(child)

    def get_current_market_results(self, all_past_markets=False):
        self._set_latest_time_slot()
        unmatched_loads = self.arrange_output(self.append_device_type(
            self.expand_to_ul_to_hours(
                self.expand_ul_to_parents(
                    self.find_unmatched_loads(self.area, {}, all_past_markets)[self.area.name],
                    self.area.name, {}
                ))), self.area)

        return unmatched_loads, self.change_name_to_uuid(unmatched_loads)

    def find_unmatched_loads(self, area, indict, all_past_markets: bool):
        """
        Aggregates list of times for each unmatched time slot for each load
        """
        indict[area.name] = {}
        for child in area.children:
            self.name_uuid_map[child.name] = child.uuid
            self.name_type_map[child.name] = child.display_type
            if child.children:
                indict[area.name] = self.find_unmatched_loads(
                    child, indict[area.name], all_past_markets
                )
            else:
                if isinstance(child.strategy, LoadHoursStrategy):
                    current_market = [child.parent.current_market] \
                        if child.parent.current_market is not None \
                        else []
                    indict[area.name][child.name] = \
                        self._calculate_unmatched_loads_leaf_area(
                            child,
                            child.parent.past_markets
                            if all_past_markets is True
                            else current_market
                        )
        return indict

    @classmethod
    def _calculate_unmatched_loads_leaf_area(cls, area, markets):
        """
        actually determines the unmatched loads
        """
        unmatched_times = []
        for market in markets:
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

    def append_device_type(self, indict):
        outdict = {}
        for name, unmatched_times in indict.items():
            outdict[name] = {
                "unmatched_loads": unmatched_times,
                "type": self.name_type_map[name]
            }
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


class MarketUnmatchedLoads:
    """
    This class is used for storing the current unmatched load results and to update them
    with new results whenever a market has been completed. It works in conjunction
    to the ExportUnmatchedLoads class, since it depends on the latter for calculating
    the unmatched loads for a market slot.
    """
    def __init__(self):
        self._unmatched_loads_incremental = {}
        self._unmatched_loads_incremental_uuid = {}

    def write_none_to_unmatched_loads(self, area, unmatched_loads, unmatched_loads_redis):
        unmatched_loads[area.name] = None
        unmatched_loads_redis[area.uuid] = None
        for child in area.children:
            self.write_none_to_unmatched_loads(child, unmatched_loads, unmatched_loads_redis)
        return unmatched_loads, unmatched_loads_redis

    @classmethod
    def _merge_base_area_unmatched_loads(cls, accumulated_results, current_results, area):
        """
        Recurses over all children (target areas) of base area and calculates the unmatched
        loads for each
        :param accumulated_results: stores the merged unmatched load results, changes by reference
        :param current_results: results for the current market, that are used to update the
        accumulated results
        :param area: area of the accumulated unmatched loads
        :return: None
        """
        for target, target_value in current_results[area].items():
            if target not in accumulated_results[area]:
                accumulated_results[area][target] = deepcopy(target_value)
            else:
                if target == 'type':
                    continue
                elif target == 'unmatched_loads':
                    cls._copy_accumulated_unmatched_loads(
                        accumulated_results, current_results, area
                    )
                else:
                    cls._merge_target_area_unmatched_loads(
                        accumulated_results, current_results, area, target
                    )

    @classmethod
    def _merge_target_area_unmatched_loads(cls, accumulated_results, current_results,
                                           area, target):
        """
        Merges the unmatched loads and unmatched times for a base area and a target area.
        :param accumulated_results: stores the merged unmatched load results, changes by reference
        :param current_results: results for the current market, that are used to update the
        accumulated results
        :param area: area of the accumulated unmatched loads
        :param target: target area of the accumulated unmatched loads
        :return: None
        """
        target_ul = accumulated_results[area][target]['unmatched_loads']
        current_ul = current_results[area][target]['unmatched_loads']
        for timestamp, ts_value in current_ul.items():
            if timestamp not in target_ul:
                target_ul[timestamp] = deepcopy(ts_value)
            else:
                if 'unmatched_times' not in current_ul[timestamp]:
                    continue
                if 'unmatched_times' not in target_ul[timestamp]:
                    target_ul[timestamp]['unmatched_times'] = {}
                for device, time_list in current_ul[timestamp]['unmatched_times'].items():
                    if device not in target_ul[timestamp]['unmatched_times']:
                        target_ul[timestamp]['unmatched_times'][device] = deepcopy(time_list)
                    else:
                        for ts in time_list:
                            if ts not in target_ul[timestamp]['unmatched_times'][device]:
                                target_ul[timestamp]['unmatched_times'][device].append(ts)

                unm_count = 0
                for _, hours in target_ul[timestamp]['unmatched_times'].items():
                    unm_count += len(hours)

                    target_ul[timestamp]['unmatched_count'] = unm_count

    @classmethod
    def _copy_accumulated_unmatched_loads(cls, accumulated_results, current_results, area):
        """
        Copies the accumulated results from the market results to the incremental results
        :param accumulated_results: stores the merged unmatched load results, changes by reference
        :param current_results: results for the current market, that are used to update the
        accumulated results
        :param area: area of the accumulated unmatched loads
        :return: None
        """
        for timestamp, ts_value in current_results[area]['unmatched_loads'].items():
            if timestamp not in accumulated_results[area]['unmatched_loads']:
                accumulated_results[area]['unmatched_loads'][timestamp] = deepcopy(ts_value)

    def _iterate_on_base_areas(self, accumulated_results, current_results):
        """
        Method which starts the merging of the current market unmatched loads with the
        existing unmatched loads (_unmatched_loads_incremental)
        :param accumulated_results: return value, stores the merged unmatched load results
        :param current_results: results for the current market, that are used to update the
        accumulated results
        :return: accumulated_results
        """
        if not self._unmatched_loads_incremental:
            return deepcopy(current_results)
        else:
            for base_area, target_results in current_results.items():
                if base_area not in accumulated_results:
                    accumulated_results[base_area] = deepcopy(target_results)
                else:
                    self._merge_base_area_unmatched_loads(
                        accumulated_results, current_results, base_area
                    )
        return accumulated_results

    def update_and_get_unmatched_loads(self, current_results, current_results_uuid):
        """
        Calculates and returns unmatched loads for the last market
        :param current_results: Output from ExportUnmatchedLoads.get_current_market_results()
        :param current_results_uuid: Output from ExportUnmatchedLoads.get_current_market_results()
        :return: Tuple with unmatched loads using area names and uuids
        """
        self._unmatched_loads_incremental = self._iterate_on_base_areas(
            self._unmatched_loads_incremental, current_results
        )
        self._unmatched_loads_incremental_uuid = self._iterate_on_base_areas(
            self._unmatched_loads_incremental_uuid, current_results_uuid
        )
        return self._unmatched_loads_incremental, self._unmatched_loads_incremental_uuid
