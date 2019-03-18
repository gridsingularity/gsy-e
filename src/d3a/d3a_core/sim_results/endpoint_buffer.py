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
    export_cumulative_loads, export_price_energy_day, generate_inter_area_trade_details, \
    export_cumulative_grid_trades_redis
from d3a.d3a_core.sim_results.file_export_endpoints import FileExportEndpoints
from d3a.d3a_core.sim_results.export_unmatched_loads import export_unmatched_loads
from d3a.d3a_core.sim_results.stats import energy_bills
from d3a.d3a_core.sim_results.device_statistics import DeviceStatistics
from d3a.d3a_core.util import convert_datetime_to_str_keys
from collections import OrderedDict
from statistics import mean


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
        self.cumulative_loads = {}
        self.price_energy_day = {}
        self.cumulative_grid_trades = {}
        self.cumulative_grid_trades_redis = {}
        self.cumulative_grid_balancing_trades = {}
        self.tree_summary = {}
        self.bills = {}
        self.bills_redis = {}
        self.balancing_energy_bills = {}
        self.trade_details = {}
        self.device_statistics = DeviceStatistics()
        self.device_statistics_time_str_dict = {}
        self.energy_trade_profile = {}

    def generate_result_report(self):
        return {
            "job_id": self.job_id,
            "random_seed": self.random_seed,
            **self.unmatched_loads_redis,
            "cumulative_loads": self.cumulative_loads,
            "price_energy_day": self.price_energy_day,
            "cumulative_grid_trades": self.cumulative_grid_trades_redis,
            "bills": self.bills_redis,
            "tree_summary": self.tree_summary,
            "status": self.status,
            "device_statistics": self.device_statistics_time_str_dict,
            "energy_trade_profile": self.energy_trade_profile
        }

    def generate_json_report(self):
        return {
            "job_id": self.job_id,
            "random_seed": self.random_seed,
            **self.unmatched_loads_redis,
            "cumulative_loads": self.cumulative_loads,
            "price_energy_day": self.price_energy_day,
            "cumulative_grid_trades": self.cumulative_grid_trades,
            "bills": self.bills,
            "tree_summary": self.tree_summary,
            "status": self.status,
            "device_statistics": self.device_statistics_time_str_dict
        }

    def update_stats(self, area, simulation_status):
        self.status = simulation_status

        self.unmatched_loads_redis = {"unmatched_loads": export_unmatched_loads(area)}
        self.unmatched_loads = {"unmatched_loads": export_unmatched_loads(area, all_devices=True)}

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

        self.cumulative_grid_trades_redis = \
            export_cumulative_grid_trades_redis(area, "past_markets")
        self.cumulative_grid_trades = export_cumulative_grid_trades(
            area, "past_markets", all_devices=True
        )
        self.cumulative_grid_balancing_trades = \
            export_cumulative_grid_trades(area, "past_balancing_markets")
        self.bills = self._update_bills(area, "past_markets")
        self.bills_redis = self._calculate_redis_bills(area, self.bills)

        self.balancing_energy_bills = self._update_bills(area, "past_balancing_markets")

        self._update_tree_summary(area)
        self.trade_details = generate_inter_area_trade_details(area, "past_markets")

        self.device_statistics.gather_device_statistics(area,
                                                        self.device_statistics.device_stats_dict)
        self.device_statistics_time_str_dict = convert_datetime_to_str_keys(
            self.device_statistics.device_stats_dict, {})

        self.energy_trade_profile = FileExportEndpoints(area).traded_energy_profile

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
        for child in area.children:
            if child.children != []:
                self._update_tree_summary(child)

    def _update_bills(self, area, past_market_types):
        result = energy_bills(area, past_market_types)
        return OrderedDict(sorted(result.items()))

    def _calculate_redis_bills(self, area, energy_bills):
        from copy import deepcopy
        flattened = self._flatten_energy_bills(deepcopy(energy_bills), {})
        return self._accumulate_by_children(area, flattened, {})

    def _flatten_energy_bills(self, energy_bills, flat_results):
        for k, v in energy_bills.items():
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
            for c in area.children:
                results.update(**self._accumulate_by_children(c, flattened, results))
        return results
