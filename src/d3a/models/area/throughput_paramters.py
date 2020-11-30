from d3a.d3a_core.util import convert_area_throughput_kVA_to_kWh
from d3a_interface.constants_limits import GlobalConfig
from d3a_interface.area_validator import validate_area


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
