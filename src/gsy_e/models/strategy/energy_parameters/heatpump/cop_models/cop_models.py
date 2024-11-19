import json
import os
from abc import abstractmethod
from enum import Enum
from typing import Optional

from gsy_framework.enums import HeatPumpSourceType


class COPModelType(Enum):
    """Selection of supported COP models"""

    UNIVERSAL = 0
    ELCO_AEROTOP_S09_IR = 1
    ELCO_AEROTOP_G07_14M = 2
    HOVAL_ULTRASOURCE_B_COMFORT_C11 = 3


MODEL_FILE_DIR = os.path.join(os.path.dirname(__file__), "model_data")

MODEL_TYPE_FILENAME_MAPPING = {
    COPModelType.ELCO_AEROTOP_S09_IR: "Elco_Aerotop_S09M-IR_model_parameters.json",
    COPModelType.ELCO_AEROTOP_G07_14M: "Elco_Aerotop_G07-14M_model_parameters.json",
    COPModelType.HOVAL_ULTRASOURCE_B_COMFORT_C11: "hoval_UltraSource_B_comfort_C_11_model_"
    "parameters.json",
}


class BaseCOPModel:
    """Base clas for COP models"""

    @abstractmethod
    def calc_cop(self, source_temp_C: float, tank_temp_C: float, heat_demand_kW: Optional[float]):
        """Return COP value for provided inputs"""


class IndividualCOPModel(BaseCOPModel):
    """Handles cop models for specific heat pump models"""

    def __init__(self, model_type: COPModelType):
        with open(
            os.path.join(MODEL_FILE_DIR, MODEL_TYPE_FILENAME_MAPPING[model_type]),
            "r",
            encoding="utf-8",
        ) as fp:
            self._model = json.load(fp)

    def _calc_power(self, source_temp_C: float, tank_temp_C: float, heat_demand_kW: float):
        CAPFT = (
            self._model["CAPFT"][0]
            + self._model["CAPFT"][1] * source_temp_C
            + self._model["CAPFT"][3] * source_temp_C**2
            + self._model["CAPFT"][2] * tank_temp_C
            + self._model["CAPFT"][5] * tank_temp_C**2
            + self._model["CAPFT"][4] * source_temp_C * tank_temp_C
        )

        HEIRFT = (
            self._model["HEIRFT"][0]
            + self._model["HEIRFT"][1] * source_temp_C
            + self._model["HEIRFT"][3] * source_temp_C**2
            + self._model["HEIRFT"][2] * tank_temp_C
            + self._model["HEIRFT"][5] * tank_temp_C**2
            + self._model["HEIRFT"][4] * source_temp_C * tank_temp_C
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

    def calc_cop(self, source_temp_C: float, tank_temp_C: float, heat_demand_kW: float):
        electrical_power_kW = self._calc_power(source_temp_C, tank_temp_C, heat_demand_kW)
        cop = heat_demand_kW / electrical_power_kW
        if cop < 0:  # on the boundaries of the training DS, this can happen
            return 1
        return heat_demand_kW / electrical_power_kW


class UniversalCOPModel(BaseCOPModel):
    """Handle cop calculation independent of the heat pump model"""

    def __init__(self, source_type: int = HeatPumpSourceType.AIR.value):
        self._source_type = source_type

    def calc_cop(
        self, source_temp_C: float, tank_temp_C: float, heat_demand_kW: Optional[float]
    ) -> float:
        """COP model following https://www.nature.com/articles/s41597-019-0199-y"""
        delta_temp = tank_temp_C - source_temp_C
        if self._source_type == HeatPumpSourceType.AIR.value:
            return 6.08 - 0.09 * delta_temp + 0.0005 * delta_temp**2
        if self._source_type == HeatPumpSourceType.GROUND.value:
            return 10.29 - 0.21 * delta_temp + 0.0012 * delta_temp**2
        assert False, "Source type not supported"


def cop_model_factory(
    model_type: COPModelType, source_type: int = HeatPumpSourceType.AIR.value
) -> BaseCOPModel:
    """Return the correct COP model."""
    if model_type == COPModelType.UNIVERSAL:
        return UniversalCOPModel(source_type)
    return IndividualCOPModel(model_type)
