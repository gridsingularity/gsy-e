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
from d3a.gsy_core.util import convert_area_throughput_kVA_to_kWh
from gsy_framework.constants_limits import GlobalConfig
from gsy_framework.area_validator import validate_area


class ThroughputParameters:
    def __init__(self,
                 baseline_peak_energy_import_kWh: float = None,
                 baseline_peak_energy_export_kWh: float = None,
                 import_capacity_kVA: float = None,
                 export_capacity_kVA: float = None):

        validate_area(baseline_peak_energy_import_kWh=baseline_peak_energy_import_kWh,
                      baseline_peak_energy_export_kWh=baseline_peak_energy_export_kWh,
                      import_capacity_kVA=import_capacity_kVA,
                      export_capacity_kVA=export_capacity_kVA)

        self.import_capacity_kVA = import_capacity_kVA
        self.export_capacity_kVA = export_capacity_kVA
        self.import_capacity_kWh = convert_area_throughput_kVA_to_kWh(import_capacity_kVA,
                                                                      GlobalConfig.slot_length)
        self.export_capacity_kWh = convert_area_throughput_kVA_to_kWh(export_capacity_kVA,
                                                                      GlobalConfig.slot_length)
        self.baseline_peak_energy_import_kWh = baseline_peak_energy_import_kWh
        self.baseline_peak_energy_export_kWh = baseline_peak_energy_export_kWh
