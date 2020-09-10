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

    def update(self, area):
        self.update_results(area)

    @staticmethod
    def _calc_results(area, baseline_value, energy_profile, direction_key):
        # as this is mainly a frontend feature,
        # the numbers are rounded for both local and redis results
        peak_percentage = \
            round_floats_for_ui(max(energy_profile.values(), default=0.0) / baseline_value * 100)
        if direction_key == "import":
            baseline_peak_energy_kWh = round_floats_for_ui(area.baseline_peak_energy_import_kWh)
        else:
            baseline_peak_energy_kWh = round_floats_for_ui(area.baseline_peak_energy_export_kWh)
        return {
            "peak_percentage": peak_percentage,
            "baseline_peak_energy_kWh": baseline_peak_energy_kWh,
         }

    @staticmethod
    def _calc_peak_energy_results(energy_profile):
        return {"peak_energy_kWh": round_floats_for_ui(max(energy_profile.values(), default=0.0))}

    @staticmethod
    def _calc_transformer_results(area, direction_key):
        if direction_key == "import":
            capacity_kWh = round_floats_for_ui(area.import_capacity_kWh)
        else:
            capacity_kWh = round_floats_for_ui(area.export_capacity_kWh)
        return {"capacity_kWh": capacity_kWh}

    def update_results(self, area):
        area_results = {"import": self._calc_peak_energy_results(area.stats.imported_energy),
                        "export": self._calc_peak_energy_results(area.stats.exported_energy)}

        baseline_import = area.baseline_peak_energy_import_kWh
        baseline_export = area.baseline_peak_energy_export_kWh
        if (baseline_import is not None and baseline_import > 0) or \
                (baseline_export is not None and baseline_export > 0):
            if baseline_import is not None and baseline_import > 0:
                area_results["import"].update(
                    self._calc_results(area, baseline_import,
                                       area.stats.imported_energy, "import")
                )
            if baseline_export is not None and baseline_export > 0:
                area_results["export"].update(
                    self._calc_results(area, baseline_export,
                                       area.stats.exported_energy, "export")
                )

        import_capacity = area.import_capacity_kWh
        export_capacity = area.export_capacity_kWh
        if import_capacity is not None and import_capacity > 0:
            area_results["import"].update(self._calc_transformer_results(area, "import"))
        if export_capacity is not None and export_capacity > 0:
            area_results["export"].update(self._calc_transformer_results(area, "export"))

        create_subdict_or_update(self.results, area.name, area_results)
        create_subdict_or_update(self.results_redis, area.uuid, area_results)

        for child in area.children:
            if child.strategy is None:
                self.update_results(child)
