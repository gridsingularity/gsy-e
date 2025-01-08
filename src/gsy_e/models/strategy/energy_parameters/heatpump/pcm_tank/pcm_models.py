class PCMChargeModel:

    def __init__(self):
        self._soc_lut = {}

    @classmethod
    def get_temp_after_charging(
        cls, current_storage_temps: list, mass_flow_kg_s: float, charging_temp: float
    ) -> list:
        return current_storage_temps

    def get_soc(self, current_storage_temps: list) -> float:
        return 0.5


class PCMDischargeModel:

    def __init__(self):
        self._soc_lut = {}

    @classmethod
    def get_temp_after_discharging(
        cls, current_storage_temps: list, mass_flow_kg_s: float, discharging_temp: float
    ) -> list:
        return current_storage_temps

    def get_soc(self, current_storage_temps: list) -> float:
        return 0.5
