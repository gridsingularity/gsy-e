import json
from enum import Enum

from gsy_framework.enums import HeatPumpSourceType
from gsy_framework.utils import convert_kWh_to_W


class COPModelType(Enum):
    UNIVERSAL = 0
    ELCO_AEROTOP_S09_IR = 1
    ELCO_AEROTOP_G07_14M = 2
    HOVAL_ULTRASOURCE_B_COMFORT_C11 = 3


MODEL_TYPE_FILENAME_MAPPING = {
    COPModelType.ELCO_AEROTOP_S09_IR: "Elco_Aerotop_S09M-IR_model_parameters.json",
    COPModelType.ELCO_AEROTOP_G07_14M: "Elco_Aerotop_G07-14M_model_parameters.json",
    COPModelType.HOVAL_ULTRASOURCE_B_COMFORT_C11: "hoval_UltraSource_B_comfort_C_11_model_"
    "parameters.json",
}


class IndividualCOPModel:

    def __init__(self, model_data_filename: str):
        with open(model_data_filename, "r") as fp:
            self._model = json.load(fp)

    def _calc_power(self, T_evap: float, T_cond: float, heat_demand_kW: float):
        CAPFT = (
            self._model["CAPFT"][0]
            + self._model["CAPFT"][1] * T_evap
            + self._model["CAPFT"][3] * T_evap**2
            + self._model["CAPFT"][2] * T_cond
            + self._model["CAPFT"][5] * T_cond**2
            + self._model["CAPFT"][4] * T_evap * T_cond
        )

        HEIRFT = (
            self._model["HEIRFT"][0]
            + self._model["HEIRFT"][1] * T_evap
            + self._model["HEIRFT"][3] * T_evap**2
            + self._model["HEIRFT"][2] * T_cond
            + self._model["HEIRFT"][5] * T_cond**2
            + self._model["HEIRFT"][4] * T_evap * T_cond
        )

        # Partial Load Ratio (PLR)
        PLR = heat_demand_kW / (self._model["Qref"] * CAPFT)

        # HEIRFPLR calculation
        HEIRFPLR = (
            self._model["HEIRFPLR"][0]
            + self._model["HEIRFPLR"][1] * PLR
            + self._model["HEIRFPLR"][2] * PLR**2
        )

        # Power consumption (P) calculation
        return self._model["Pref"] * CAPFT * HEIRFT * HEIRFPLR

    def _calc_q(self, T_evap: float, T_cond: float, power_kW: float):
        return 0.0

    def calc_cop(self, source_temp: float, tank_temp: float, energy_consumption: float):
        power_consumption = convert_kWh_to_W(energy_consumption) / 1000
        heat_demanded = self._calc_q(source_temp, tank_temp, power_consumption)
        return heat_demanded / power_consumption


class COPModels:

    def __init__(self, model_type: COPModelType, source_type: int = HeatPumpSourceType.AIR.value):

        self._model_type = model_type
        self._source_type = source_type
        self.individual_model: IndividualCOPModel = (
            None
            if model_type != COPModelType.UNIVERSAL.value
            else IndividualCOPModel(MODEL_TYPE_FILENAME_MAPPING[model_type])
        )

    def get_cop(self, source_temp: float, tank_temp: float, energy_consumption: float) -> float:

        if self._model_type == COPModelType.UNIVERSAL:
            return self._get_universal_cop(source_temp, tank_temp)
        else:
            return self.individual_model.calc_cop(source_temp, tank_temp, energy_consumption)

    def _get_universal_cop(self, source_temp: float, tank_temp: float) -> float:
        """COP model following https://www.nature.com/articles/s41597-019-0199-y"""
        delta_temp = tank_temp - source_temp
        if self._source_type == HeatPumpSourceType.AIR.value:
            return 6.08 - 0.09 * delta_temp + 0.0005 * delta_temp**2
        if self._source_type == HeatPumpSourceType.GROUND.value:
            return 10.29 - 0.21 * delta_temp + 0.0012 * delta_temp**2
