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
from d3a.d3a_core.util import area_name_from_area_or_iaa_name,  round_floats_for_ui, \
    add_or_create_key, create_subdict_or_update, area_sells_to_child, child_buys_from_area


class AreaThroughputStats:
    def __init__(self):
        self.results = {}
        self.results_redis = {}
        self.exported_energy = {}
        self.imported_energy = {}

    def update(self, area):
        self.update_results(area)

    def _calc_results(self, area, baseline_value, energy_profile, direction_key):
        if len(energy_profile.keys()) > 0:
            # as this is mainly a frontend feature,
            # the numbers are rounded for both local and redis results
            out_dict = {direction_key: {
                "peak_energy_kWh": round_floats_for_ui(max(energy_profile.values())),
                "peak_percentage": round_floats_for_ui(max(energy_profile.values()) /
                                                       baseline_value * 100)
                                     }}
            create_subdict_or_update(self.results, area.name, out_dict)
            create_subdict_or_update(self.results_redis, area.uuid, out_dict)

    def update_results(self, area):
        baseline_import = area.baseline_peak_energy_import_kWh
        baseline_export = area.baseline_peak_energy_export_kWh
        if (baseline_import is not None and baseline_import > 0) or \
                (baseline_export is not None and baseline_export > 0):
            self.aggregate_exported_imported_energy(area)
            if baseline_import is not None and baseline_import > 0:
                self._calc_results(area, baseline_import, self.imported_energy, "import")
            if baseline_export is not None and baseline_export > 0:
                self._calc_results(area, baseline_export, self.exported_energy, "export")
        for child in area.children:
            if child.strategy is None:
                self.update_results(child)

    def aggregate_exported_imported_energy(self, area):
        past_markets = list(area._markets.past_markets.values())
        if len(past_markets) > 0:
            current_market = past_markets[-1]
        else:
            return
        child_names = [area_name_from_area_or_iaa_name(c.name) for c in area.children]
        for trade in current_market.trades:
            if child_buys_from_area(trade, area.name, child_names):
                add_or_create_key(self.exported_energy, current_market.time_slot_str,
                                  trade.offer.energy)
            if area_sells_to_child(trade, area.name, child_names):
                add_or_create_key(self.imported_energy, current_market.time_slot_str,
                                  trade.offer.energy)
        if current_market.time_slot_str not in self.imported_energy:
            self.imported_energy[current_market.time_slot_str] = 0.
        if current_market.time_slot_str not in self.exported_energy:
            self.exported_energy[current_market.time_slot_str] = 0.
