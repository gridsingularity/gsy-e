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
from d3a.d3a_core.sim_results.area_statistics import export_cumulative_grid_trades, \
    export_cumulative_grid_trades_redis, export_cumulative_loads, export_price_energy_day, \
    generate_inter_area_trade_details, MarketPriceEnergyDay
from d3a.d3a_core.sim_results.file_export_endpoints import FileExportEndpoints
from d3a.d3a_core.sim_results.stats import MarketEnergyBills
from d3a.d3a_core.sim_results.device_statistics import DeviceStatistics
from d3a.d3a_core.util import convert_datetime_to_str_keys, round_floats_for_ui
from d3a.d3a_core.sim_results.export_unmatched_loads import ExportUnmatchedLoads, \
    MarketUnmatchedLoads
from d3a.models.const import ConstSettings
from collections import OrderedDict
from statistics import mean
from copy import deepcopy

_NO_VALUE = {
    'min': None,
    'avg': None,
    'max': None
}


class SimulationEndpointBuffer:
    def __init__(self, job_id, initial_params):
        self.job_id = job_id
        self.random_seed = initial_params["seed"] if initial_params["seed"] is not None else ''
        self.status = {}
        self.unmatched_loads = {}
        self.unmatched_loads_redis = {}
        self.market_unmatched_loads = MarketUnmatchedLoads()
        self.cumulative_loads = {}
        self.price_energy_day = {}
        self.market_price_energy_day = MarketPriceEnergyDay()
        self.cumulative_grid_trades = {}
        self.accumulated_trades = {}
        self.accumulated_trades_redis = {}
        self.accumulated_balancing_trades = {}
        self.cumulative_grid_trades_redis = {}
        self.cumulative_grid_balancing_trades = {}
        self.tree_summary = {}
        self.tree_summary_redis = {}
        self.market_bills = MarketEnergyBills()
        self.bills = {}
        self.bills_redis = {}
        self.balancing_energy_bills = {}
        self.trade_details = {}
        self.device_statistics = DeviceStatistics()
        self.device_statistics_time_str_dict = {}
        self.energy_trade_profile = {}
        self.energy_trade_profile_redis = {}
        self.file_export_endpoints = FileExportEndpoints()

    def generate_result_report(self):
        return {
            "job_id": self.job_id,
            "random_seed": self.random_seed,
            "unmatched_loads": self.unmatched_loads_redis,
            "cumulative_loads": self.cumulative_loads,
            "price_energy_day": self.price_energy_day,
            "cumulative_grid_trades": self.cumulative_grid_trades_redis,
            "bills": self.bills_redis,
            "tree_summary": self.tree_summary_redis,
            "status": self.status,
            "device_statistics": self.device_statistics_time_str_dict,
            "energy_trade_profile": self.energy_trade_profile_redis
        }

    def generate_json_report(self):
        return {
            "job_id": self.job_id,
            "random_seed": self.random_seed,
            "unmatched_loads": self.unmatched_loads,
            "cumulative_loads": self.cumulative_loads,
            "price_energy_day": self.price_energy_day,
            "cumulative_grid_trades": self.cumulative_grid_trades,
            "bills": self.bills,
            "tree_summary": self.tree_summary,
            "status": self.status,
            "device_statistics": self.device_statistics_time_str_dict,
            "energy_trade_profile": self.energy_trade_profile
        }

    def _update_unmatched_loads(self, area):
        if ConstSettings.GeneralSettings.KEEP_PAST_MARKETS:
            self.unmatched_loads, self.unmatched_loads_redis = ExportUnmatchedLoads(area)()
        else:
            self.unmatched_loads, self.unmatched_loads_redis = \
                self.market_unmatched_loads.update_and_get_unmatched_loads(area)

    def _update_price_energy_day(self, area):
        if ConstSettings.GeneralSettings.KEEP_PAST_MARKETS:
            self.price_energy_day = {
                "price-currency": "Euros",
                "load-unit": "kWh",
                "price-energy-day": export_price_energy_day(area)
            }
        else:
            self.price_energy_day = self.market_price_energy_day.update_and_get_last_past_market(
                area
            )

    def _update_cumulative_grid_trades(self, area):
        market_type = \
            "past_markets" if ConstSettings.GeneralSettings.KEEP_PAST_MARKETS else "current_market"
        balancing_market_type = "past_balancing_markets" \
            if ConstSettings.GeneralSettings.KEEP_PAST_MARKETS \
            else "current_balancing_market"

        if ConstSettings.GeneralSettings.KEEP_PAST_MARKETS:
            self.accumulated_trades = {}
            self.accumulated_trades_redis = {}
            self.accumulated_balancing_trades = {}

        self.accumulated_trades_redis, self.cumulative_grid_trades_redis = \
            export_cumulative_grid_trades_redis(area, self.accumulated_trades_redis,
                                                market_type)
        self.accumulated_trades, self.cumulative_grid_trades = \
            export_cumulative_grid_trades(area, self.accumulated_trades,
                                          market_type, all_devices=True)
        self.accumulated_balancing_trades, self.cumulative_grid_balancing_trades = \
            export_cumulative_grid_trades(area, self.accumulated_balancing_trades,
                                          balancing_market_type)

    def update_stats(self, area, simulation_status):
        self.status = simulation_status
        self._update_unmatched_loads(area)
        self._update_price_energy_day(area)
        self.cumulative_loads = {
            "price-currency": "Euros",
            "load-unit": "kWh",
            "cumulative-load-price": export_cumulative_loads(area)
        }
        self.price_energy_day = {
            "price-currency": "Euros",
            "load-unit": "kWh",
            "price-energy-day": export_price_energy_day(area)
        }

        self._update_cumulative_grid_trades(area)

        self.bills = self._update_bills(area, "past_markets")
        self.bills_redis = self._calculate_redis_bills(area, self.bills)

        self.balancing_energy_bills = self._update_bills(area, "past_balancing_markets")

        self._update_tree_summary(area)
        self.trade_details = generate_inter_area_trade_details(area, "past_markets")

        self.device_statistics.gather_device_statistics(area,
                                                        self.device_statistics.device_stats_dict)
        self.device_statistics_time_str_dict = convert_datetime_to_str_keys(
            self.device_statistics.device_stats_dict, {})

        self.file_export_endpoints(area)
        self.energy_trade_profile = self.file_export_endpoints.traded_energy_profile
        self.energy_trade_profile_redis = self._round_energy_trade_profile(
            self.file_export_endpoints.traded_energy_profile_redis)

    def _update_tree_summary(self, area):
        price_energy_list = export_price_energy_day(area)

        def calculate_prices(key, functor):
            # Need to convert to euro cents to avoid having to change the backend
            # TODO: Both this and the frontend have to remove the recalculation
            energy_prices = [price_energy[key] for price_energy in price_energy_list]
            return round(100 * functor(energy_prices), 2) if len(energy_prices) > 0 else 0.0

        self.tree_summary[area.slug] = {
            "min_trade_price": calculate_prices("min_price", min),
            "max_trade_price": calculate_prices("max_price", max),
            "avg_trade_price": calculate_prices("av_price", mean),
        }
        self.tree_summary_redis[area.uuid] = self.tree_summary[area.slug]
        for child in area.children:
            if child.children != []:
                self._update_tree_summary(child)

    def _update_bills(self, area, past_market_types):
        result = self.market_bills.update(area, past_market_types)
        return OrderedDict(sorted(result.items()))

    def _calculate_redis_bills(self, area, energy_bills):
        flattened = self._flatten_energy_bills(deepcopy(energy_bills), {})
        return self._accumulate_by_children(area, flattened, {})

    def _flatten_energy_bills(self, energy_bills, flat_results):
        for k, v in energy_bills.items():
            if k == "market_fee":
                continue
            if "children" in v:
                self._flatten_energy_bills(v["children"], flat_results)
            flat_results[k] = v
            flat_results[k].pop("children", None)
        return flat_results

    def _accumulate_by_children(self, area, flattened, results):
        if not area.children:
            # This is a device
            results[area.uuid] = flattened[area.name]
        else:
            results[area.uuid] = [
                {c.name: flattened[c.name]}
                for c in area.children
            ]
            results.update(**self._generate_external_and_total_bills(area, results, flattened))

            for c in area.children:
                results.update(
                    **self._accumulate_by_children(c, flattened, results)
                )
        return results

    @classmethod
    def _round_energy_trade_profile(cls, profile):
        for k in profile.keys():
            for sold_bought in ['sold_energy', 'bought_energy']:
                for dev in profile[k][sold_bought].keys():
                    for target in profile[k][sold_bought][dev].keys():
                        for timestamp in profile[k][sold_bought][dev][target].keys():
                            profile[k][sold_bought][dev][target][timestamp] = round_floats_for_ui(
                                profile[k][sold_bought][dev][target][timestamp])
        return profile

    @classmethod
    def _round_area_bill_result_redis(cls, results):
        for i, _ in enumerate(results):
            for k in results[i].keys():
                results[i][k]['bought'] = round_floats_for_ui(results[i][k]['bought'])
                results[i][k]['sold'] = round_floats_for_ui(results[i][k]['sold'])
                results[i][k]['spent'] = round_floats_for_ui(results[i][k]['spent'])
                results[i][k]['earned'] = round_floats_for_ui(results[i][k]['earned'])
                results[i][k]['total_energy'] = round_floats_for_ui(results[i][k]['total_energy'])
                results[i][k]['total_cost'] = round_floats_for_ui(results[i][k]['total_cost'])
        return results

    def _generate_external_and_total_bills(self, area, results, flattened):
        all_child_results = [v for i in results[area.uuid] for _, v in i.items()]
        results[area.uuid].append({"Accumulated Trades": {
            'bought': sum(v['bought'] for v in all_child_results),
            'sold': sum(v['sold'] for v in all_child_results),
            'spent': sum(v['spent'] for v in all_child_results),
            'earned': sum(v['earned'] for v in all_child_results),
            'total_energy': sum(v['total_energy'] for v in all_child_results),
            'total_cost': sum(v['total_cost'] for v in all_child_results),
        }})

        if area.name in flattened:
            results[area.uuid].append({"External Trades": flattened[area.name]})
        results[area.uuid] = self._round_area_bill_result_redis(results[area.uuid])
        return results
