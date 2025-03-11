from pendulum import duration


class PCMModelBase:

    def __init__(self, slot_length: duration, mass_flow_rate_kg_s: float):
        self._mass_flow_rate = mass_flow_rate_kg_s
        self._slot_length = slot_length

    @property
    def _soc_lut(self):
        return {}

    @property
    def _soc_lut_key(self) -> str:
        return ""

    def get_soc(self, current_storage_temps: list):
        return 50


class PCMChargeModel(PCMModelBase):

    @property
    def _soc_lut(self):
        return {}

    def get_temp_after_charging(self, current_storage_temps: list, charging_temp: float) -> list:
        return current_storage_temps


class PCMDischargeModel(PCMModelBase):

    @property
    def _soc_lut(self):
        return {}

    def get_temp_after_discharging(
        self, current_storage_temps: list, discharging_temp: float
    ) -> list:
        return current_storage_temps
