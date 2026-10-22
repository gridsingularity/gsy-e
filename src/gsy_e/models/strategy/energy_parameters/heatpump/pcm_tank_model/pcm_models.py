from pendulum import duration
from gsy_e.models.strategy.energy_parameters.heatpump.tank_parameters import PCMType


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

    def __init__(
        self, slot_length: duration, mass_flow_rate_kg_s: float, pcm_type: PCMType = PCMType.OM42
    ):

        super().__init__(slot_length, mass_flow_rate_kg_s)

    @property
    def _soc_lut(self):
        return {}

    def get_temp_after_charging(
        self, current_htf_temps_C: list, current_pcm_temps_C: list, charging_temp: float
    ) -> tuple[list, list]:
        return current_htf_temps_C, current_pcm_temps_C


class PCMDischargeModel(PCMModelBase):

    def __init__(
        self, slot_length: duration, mass_flow_rate_kg_s: float, pcm_type: PCMType = PCMType.OM42
    ):
        super().__init__(slot_length, mass_flow_rate_kg_s)

    @property
    def _soc_lut(self):
        return {}

    def get_temp_after_discharging(
        self, current_htf_temps_C: list, current_pcm_temps_C: list, discharging_temp: float
    ) -> tuple[list, list]:
        return current_htf_temps_C, current_pcm_temps_C
