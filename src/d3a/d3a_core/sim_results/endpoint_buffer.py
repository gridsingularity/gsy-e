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
    export_cumulative_grid_trades_redis, export_cumulative_loads, MarketPriceEnergyDay, \
    generate_inter_area_trade_details
from d3a.d3a_core.sim_results.file_export_endpoints import FileExportEndpoints
from d3a.d3a_core.sim_results.stats import energy_bills
from d3a.d3a_core.sim_results.device_statistics import DeviceStatistics
from d3a.d3a_core.util import round_floats_for_ui
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
        self.price_energy_day = MarketPriceEnergyDay()
        self.cumulative_grid_trades = {}
        self.accumulated_trades = {}
        self.accumulated_trades_redis = {}
        self.accumulated_balancing_trades = {}
        self.cumulative_grid_trades_redis = {}
        self.cumulative_grid_balancing_trades = {}
        self.tree_summary = {}
        self.tree_summary_redis = {}
        self.bills = {}
        self.bills_redis = {}
        self.balancing_energy_bills = {}
        self.trade_details = {}
        self.device_statistics = DeviceStatistics()
        self.energy_trade_profile = {}
        self.energy_trade_profile_redis = {}
        self.file_export_endpoints = FileExportEndpoints()

    def generate_result_report(self):
        return {
            "job_id": self.job_id,
            "random_seed": self.random_seed,
            "unmatched_loads": self.unmatched_loads_redis,
            "cumulative_loads": self.cumulative_loads,
            "price_energy_day": self.price_energy_day.redis_output,
            "cumulative_grid_trades": self.cumulative_grid_trades_redis,
            "bills": self.bills_redis,
            "tree_summary": self.tree_summary_redis,
            "status": self.status,
            "device_statistics": self.device_statistics.flat_results_time_str,
            "energy_trade_profile": self.energy_trade_profile_redis
        }

    def generate_json_report(self):
        return {
            "job_id": self.job_id,
            "random_seed": self.random_seed,
            "unmatched_loads": self.unmatched_loads,
            "cumulative_loads": self.cumulative_loads,
            "price_energy_day": self.price_energy_day.csv_output,
            "cumulative_grid_trades": self.cumulative_grid_trades,
            "bills": self.bills,
            "tree_summary": self.tree_summary,
            "status": self.status,
            "device_statistics": self.device_statistics.device_stats_time_str,
            "energy_trade_profile": self.energy_trade_profile
        }

    def _update_unmatched_loads(self, area):
        if ConstSettings.GeneralSettings.KEEP_PAST_MARKETS:
            self.unmatched_loads, self.unmatched_loads_redis = ExportUnmatchedLoads(area)()
        else:
            self.unmatched_loads, self.unmatched_loads_redis = \
                self.market_unmatched_loads.update_and_get_unmatched_loads(area)

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
        # Should always precede tree-summary update
        self.price_energy_day.update(area)
        self.cumulative_loads = {
            "price-currency": "Euros",
            "load-unit": "kWh",
            "cumulative-load-price": export_cumulative_loads(area)
        }

        self._update_cumulative_grid_trades(area)

        self.bills = self._update_bills(area, "past_markets")
        self._bills_for_redis(area)

        self.balancing_energy_bills = self._update_bills(area, "past_balancing_markets")

        self._update_tree_summary(area)
        self.trade_details = generate_inter_area_trade_details(area, "past_markets")

        self.device_statistics.update(area)

        self.file_export_endpoints(area)
        self.energy_trade_profile = self.file_export_endpoints.traded_energy_profile
        self.energy_trade_profile_redis = self._round_energy_trade_profile(
            self.file_export_endpoints.traded_energy_profile_redis)

    def _update_tree_summary(self, area):
        price_energy_list = self.price_energy_day.csv_output

        def calculate_prices(key, functor):
            if area.name not in price_energy_list:
                return 0.
            energy_prices = [
                price_energy[key]
                for price_energy in price_energy_list[area.name]["price-energy-day"]
            ]
            return round(functor(energy_prices), 2) if len(energy_prices) > 0 else 0.0

        self.tree_summary[area.slug] = {
            "min_trade_price": calculate_prices("min_price", min),
            "max_trade_price": calculate_prices("max_price", max),
            "avg_trade_price": calculate_prices("av_price", mean),
        }
        self.tree_summary_redis[area.uuid] = self.tree_summary[area.slug]
        for child in area.children:
            if child.children:
                self._update_tree_summary(child)

    def _update_bills(self, area, past_market_types):
        result = energy_bills(area, past_market_types)
        flattened = self._flatten_energy_bills(OrderedDict(sorted(result.items())), {})
        return self._accumulate_by_children(area, flattened, {})

    def _bills_for_redis(self, area):
        if area.name in self.bills:
            self.bills_redis[area.uuid] = \
                self._round_area_bill_result_redis(deepcopy(self.bills[area.name]))
        for child in area.children:
            if child.children:
                self._bills_for_redis(child)
            elif child.name in self.bills:
                self.bills_redis[child.uuid] = \
                    self._round_child_bill_results(self.bills[child.name])

    def _flatten_energy_bills(self, energy_bills, flat_results):
        for k, v in energy_bills.items():
            if k == "market_fee":
                flat_results["market_fee"] = v
                continue
            if "children" in v:
                self._flatten_energy_bills(v["children"], flat_results)
            flat_results[k] = v
            flat_results[k].pop("children", None)
        return flat_results

    def _accumulate_by_children(self, area, flattened, results):
        if not area.children:
            # This is a device
            results[area.name] = flattened[area.name]
        else:
            results[area.name] = {c.name: flattened[c.name] for c in area.children}

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
    def _round_child_bill_results(self, results):
        results['bought'] = round_floats_for_ui(results['bought'])
        results['sold'] = round_floats_for_ui(results['sold'])
        results['spent'] = round_floats_for_ui(results['spent'])
        results['earned'] = round_floats_for_ui(results['earned'])
        results['total_energy'] = round_floats_for_ui(results['total_energy'])
        results['total_cost'] = round_floats_for_ui(results['total_cost'])
        if "market_fee" in results:
            results["market_fee"] = round_floats_for_ui(results['market_fee'])
        return results

    @classmethod
    def _round_area_bill_result_redis(cls, results):
        for k in results.keys():
            results[k] = cls._round_child_bill_results(results[k])
        return results

    def _generate_external_and_total_bills(self, area, results, flattened):
        all_child_results = [v for v in results[area.name].values()]
        results[area.name].update({"Accumulated Trades": {
            'bought': sum(v['bought'] for v in all_child_results),
            'sold': sum(v['sold'] for v in all_child_results),
            'spent': sum(v['spent'] for v in all_child_results),
            'earned': sum(v['earned'] for v in all_child_results),
            'total_energy': sum(v['total_energy'] for v in all_child_results),
            'total_cost': sum(v['total_cost'] for v in all_child_results),
            'market_fee': flattened[area.name]["market_fee"]
            if area.name in flattened else flattened["market_fee"]
        }})

        if area.name in flattened:
            external = {k: v for k, v in flattened[area.name].items() if k != 'market_fee'}
            results[area.name].update({"External Trades": external})
        return results
