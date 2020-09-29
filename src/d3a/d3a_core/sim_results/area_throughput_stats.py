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
from d3a.d3a_core.util import round_floats_for_ui, create_subdict_or_update, \
    area_name_from_area_or_iaa_name, child_buys_from_area, add_or_create_key, area_sells_to_child


class AreaThroughputStats:
    def __init__(self):
        self.results = {}
        self.results_redis = {}
        self.exported_energy = {}
        self.imported_energy = {}

    def update(self, area_dict, core_stats, current_market_time_slot_str):
        self.update_results(area_dict, core_stats, current_market_time_slot_str)

    @staticmethod
    def _calc_peak_energy_results(energy_profile):
        return {"peak_energy_kWh": round_floats_for_ui(max(energy_profile.values(), default=0.0))}

    def update_results(self, area_dict, core_stats, current_market_time_slot_str):
        self.aggregate_exported_imported_energy(area_dict, core_stats,
                                                current_market_time_slot_str)
        area_results = {
            "import": self._calc_peak_energy_results(self.imported_energy[area_dict['uuid']]),
            "export": self._calc_peak_energy_results(self.exported_energy[area_dict['uuid']])
        }
        area_throughput = core_stats.get(area_dict['uuid'], {}).get('area_throughput', {})

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

        create_subdict_or_update(self.results, area_dict['name'], area_results)
        create_subdict_or_update(self.results_redis, area_dict['uuid'], area_results)

        for child in area_dict['children']:
            if child['type'] == "Area":
                self.update_results(child, core_stats, current_market_time_slot_str)

    def aggregate_exported_imported_energy(self, area_dict, core_stats,
                                           current_market_time_slot_str):
        if current_market_time_slot_str is None:
            return

        if area_dict['uuid'] not in self.imported_energy:
            self.imported_energy[area_dict['uuid']] = {}
        if area_dict['uuid'] not in self.exported_energy:
            self.exported_energy[area_dict['uuid']] = {}

        child_names = [area_name_from_area_or_iaa_name(c['name']) for c in area_dict['children']]
        for trade in core_stats.get(area_dict['uuid'], {}).get('trades', []):
            if child_buys_from_area(trade, area_dict['name'], child_names):
                add_or_create_key(self.exported_energy[area_dict['uuid']],
                                  current_market_time_slot_str,
                                  trade['energy'])
            if area_sells_to_child(trade, area_dict['name'], child_names):
                add_or_create_key(self.imported_energy[area_dict['uuid']],
                                  current_market_time_slot_str,
                                  trade['energy'])
