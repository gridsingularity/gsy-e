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
from d3a.d3a_core.util import round_floats_for_ui, create_subdict_or_update


class AreaThroughputStats:
    def __init__(self):
        self.results = {}
        self.results_redis = {}
        self.exported_energy = {}
        self.imported_energy = {}

    def update(self, area_dict, core_stats, current_market_time_slot_str):
        if current_market_time_slot_str == "":
            return
        self.results = {}
        self.results_redis = {}
        self.update_results(area_dict, core_stats, current_market_time_slot_str)

    def update_results(self, area_dict, core_stats, current_market_time_slot_str):
        area_throughput = core_stats.get(area_dict['uuid'], {}).get('area_throughput', {})
        imported_peak = round_floats_for_ui(area_throughput.get('imported_energy_kWh', 0.))
        exported_peak = round_floats_for_ui(area_throughput.get('exported_energy_kWh', 0.))
        net_peak = round_floats_for_ui(area_throughput.get('net_energy_flow_kWh', 0.))
        area_results = {
            "import": {'peak_energy_kWh': imported_peak},
            "export": {'peak_energy_kWh': exported_peak},
            "net_energy_flow": {'peak_energy_kWh': net_peak}
        }

        baseline_import = area_throughput.get('baseline_peak_energy_import_kWh', None)
        baseline_export = area_throughput.get('baseline_peak_energy_export_kWh', None)
        if (baseline_import is not None and baseline_import > 0) or \
                (baseline_export is not None and baseline_export > 0):
            if baseline_import is not None and baseline_import > 0:
                peak_percentage = round_floats_for_ui(
                    area_results['import']['peak_energy_kWh'] / baseline_import * 100
                )
                area_results["import"].update(
                    {'peak_percentage': peak_percentage,
                     'baseline_peak_energy_kWh': baseline_import}
                )
            if baseline_export is not None and baseline_export > 0:
                peak_percentage = round_floats_for_ui(
                    area_results['export']['peak_energy_kWh'] / baseline_export * 100
                )
                area_results["export"].update(
                    {'peak_percentage': peak_percentage,
                     'baseline_peak_energy_kWh': baseline_export}
                )

        import_capacity = area_throughput.get('import_capacity_kWh', None)
        export_capacity = area_throughput.get('export_capacity_kWh', None)
        if import_capacity is not None and import_capacity > 0:
            area_results["import"].update(
                {'capacity_kWh': round_floats_for_ui(import_capacity)}
            )
        if export_capacity is not None and export_capacity > 0:
            area_results["export"].update(
                {'capacity_kWh': round_floats_for_ui(export_capacity)}
            )
        area_throughput_profile = {}
        area_throughput_profile[current_market_time_slot_str] = area_results

        create_subdict_or_update(self.results, area_dict['name'], area_throughput_profile)
        create_subdict_or_update(self.results_redis, area_dict['uuid'], area_throughput_profile)

        for child in area_dict['children']:
            if child['type'] == "Area":
                self.update_results(child, core_stats, current_market_time_slot_str)
