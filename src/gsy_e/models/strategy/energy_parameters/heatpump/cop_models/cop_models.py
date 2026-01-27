import json
import os
from abc import abstractmethod
from enum import Enum
from logging import getLogger
from typing import Optional

import sympy as sp
from gsy_framework.constants_limits import FLOATING_POINT_TOLERANCE
from gsy_framework.enums import HeatPumpSourceType

log = getLogger(__name__)


class COPModelType(Enum):
    """Selection of supported COP models"""

    UNIVERSAL = 0
    ELCO_AEROTOP_S09_IR = 1
    ELCO_AEROTOP_G07_14M = 2
    HOVAL_ULTRASOURCE_B_COMFORT_C11 = 3
    AERMEC_NXP_0600_4L_HEAT = 4
    AERMEC_NXP_0600_4L_COOL = 5


MODEL_FILE_DIR = os.path.join(os.path.dirname(__file__), "model_data")

MODEL_TYPE_FILENAME_MAPPING = {
    COPModelType.ELCO_AEROTOP_S09_IR: "Elco_Aerotop_S09M-IR_model_parameters.json",
    COPModelType.ELCO_AEROTOP_G07_14M: "Elco_Aerotop_G07-14M_model_parameters.json",
    COPModelType.HOVAL_ULTRASOURCE_B_COMFORT_C11: "hoval_UltraSource_B_comfort_C_11_model_"
    "parameters.json",
    COPModelType.AERMEC_NXP_0600_4L_HEAT: "AERMEC_NXP_0600_4L_HEAT_model_parameters.json",
    COPModelType.AERMEC_NXP_0600_4L_COOL: "AERMEC_NXP_0600_4L_COOL_model_parameters.json",
}


class BaseCOPModel:
    """Base clas for COP models"""

    @abstractmethod
    def calc_cop(
        self,
        source_temp_C: float,
        condenser_temp_C: float,
        heat_demand_kW: Optional[float] = None,
    ):
        """Return COP value for provided inputs"""

    @abstractmethod
    def calc_q_from_p_kW(
        self,
        source_temp_C: float,
        condenser_temp_C: float,
        electrical_demand_kW: Optional[float] = None,
    ):
        """Calculate heat energy from provided inputs."""


class IndividualCOPModel(BaseCOPModel):
    """Handles cop models for specific heat pump models"""

    def __init__(self, model_type: COPModelType):
        with open(
            os.path.join(MODEL_FILE_DIR, MODEL_TYPE_FILENAME_MAPPING[model_type]),
            "r",
            encoding="utf-8",
        ) as fp:
            self._model = json.load(fp)
        self.model_type = model_type

    def _calc_power(self, source_temp_C: float, condenser_temp_C: float, heat_demand_kW: float):
        CAPFT = (
            self._model["CAPFT"][0]
            + self._model["CAPFT"][1] * source_temp_C
            + self._model["CAPFT"][3] * source_temp_C**2
            + self._model["CAPFT"][2] * condenser_temp_C
            + self._model["CAPFT"][5] * condenser_temp_C**2
            + self._model["CAPFT"][4] * source_temp_C * condenser_temp_C
        )

        HEIRFT = (
            self._model["HEIRFT"][0]
            + self._model["HEIRFT"][1] * source_temp_C
            + self._model["HEIRFT"][3] * source_temp_C**2
            + self._model["HEIRFT"][2] * condenser_temp_C
            + self._model["HEIRFT"][5] * condenser_temp_C**2
            + self._model["HEIRFT"][4] * source_temp_C * condenser_temp_C
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

    def _resolve_heat(
        self, source_temp_C: float, condenser_temp_C: float, electricity_demand_kW: float
    ):
        CAPFT = (
            self._model["CAPFT"][0]
            + self._model["CAPFT"][1] * source_temp_C
            + self._model["CAPFT"][3] * source_temp_C**2
            + self._model["CAPFT"][2] * condenser_temp_C
            + self._model["CAPFT"][5] * condenser_temp_C**2
            + self._model["CAPFT"][4] * source_temp_C * condenser_temp_C
        )

        HEIRFT = (
            self._model["HEIRFT"][0]
            + self._model["HEIRFT"][1] * source_temp_C
            + self._model["HEIRFT"][3] * source_temp_C**2
            + self._model["HEIRFT"][2] * condenser_temp_C
            + self._model["HEIRFT"][5] * condenser_temp_C**2
            + self._model["HEIRFT"][4] * source_temp_C * condenser_temp_C
        )

        # Partial Load Ratio (PLR)
        Q = sp.symbols("Q")
        PLR = Q / (self._model["Qref"] * CAPFT)

        # HEIRFPLR calculation
        HEIRFPLR = (
            self._model["HEIRFPLR"][0]
            + self._model["HEIRFPLR"][1] * PLR
            + self._model["HEIRFPLR"][2] * PLR**2
        )

        solutions = sp.solve(
            sp.Eq(electricity_demand_kW, self._model["Pref"] * CAPFT * HEIRFT * HEIRFPLR), Q
        )
        Q = self._select_Q_solution(solutions, CAPFT)
        if Q is None:
            # fallback: use median COP of training dataset to calculate Q
            Q = self._model["COP_med"] * electricity_demand_kW
        return Q

    def _select_Q_solution(self, Q_solutions, CAPFT) -> Optional[float]:
        """
        Selects the correct Q and PLR solution based on:
        - PLR = Q / (Qref * fCAPFT)
        - both PLRs must be between 0 and 1
        - the correct branch is the one with the LARGER PLR
          (as indicated by the training dataset)
        """

        PLR_dict = {
            q / (self._model["Qref"] * CAPFT): q
            for q in Q_solutions
            if 0 <= q / (self._model["Qref"] * CAPFT) <= 1
        }
        if not PLR_dict:
            PLR_list = [q / (self._model["Qref"] * CAPFT) for q in Q_solutions]
            log.error(
                "IndividualCOPModel: No physically feasible PLR solutions Q: %s, PLR: %s ",
                Q_solutions,
                PLR_list,
            )
            return None
        return float(PLR_dict[max(PLR_dict)])

    def _limit_heat_demand_kW(self, heat_demand_kW: float) -> float:
        assert heat_demand_kW is not None, "heat demand should be provided"
        if heat_demand_kW > self._model["Q_max"]:
            log.error(
                "calc_cop: heat demand (%s kW) exceeds maximum heat_demand_kW: %s",
                heat_demand_kW,
                self._model["Q_max"],
            )
            return self._model["Q_max"]
        if heat_demand_kW < self._model["Q_min"]:
            log.error(
                "calc_cop: heat demand (%s kW) exceeds minimum heat_demand_kW: %s",
                heat_demand_kW,
                self._model["Q_min"],
            )
            return self._model["Q_min"]
        return heat_demand_kW

    def calc_q_from_p_kW(
        self,
        source_temp_C: float,
        condenser_temp_C: float,
        electrical_demand_kW: Optional[float] = None,
    ):
        return self._resolve_heat(
            source_temp_C=source_temp_C,
            condenser_temp_C=condenser_temp_C,
            electricity_demand_kW=electrical_demand_kW,
        )

    def calc_cop(
        self,
        source_temp_C: float,
        condenser_temp_C: float,
        heat_demand_kW: Optional[float] = None,
    ):
        heat_demand_kW = self._limit_heat_demand_kW(heat_demand_kW)
        if heat_demand_kW < FLOATING_POINT_TOLERANCE:
            return 0
        electrical_power_kW = self._calc_power(source_temp_C, condenser_temp_C, heat_demand_kW)
        if electrical_power_kW <= 0:
            log.error(
                "calculated power is negative: "
                "hp model: %s  source_temp: %s, "
                "condenser_temp: %s, heat_demand_kW: %s, calculated power: %s",
                self.model_type.name,
                round(source_temp_C, 2),
                round(condenser_temp_C, 2),
                round(heat_demand_kW, 2),
                round(electrical_power_kW, 2),
            )
            return 0
        cop = heat_demand_kW / electrical_power_kW
        if cop > self._model["COP_max"] or cop < self._model["COP_min"]:
            log.error(
                "calculated COP (%s) is unrealistic: "
                "hp model: %s  source_temp: %s, "
                "condenser_temp: %s, heat_demand_kW: %s, calculated power: %s",
                round(cop, 2),
                self.model_type.name,
                round(source_temp_C, 2),
                round(condenser_temp_C, 2),
                round(heat_demand_kW, 2),
                round(electrical_power_kW, 2),
            )
        return cop


class UniversalCOPModel(BaseCOPModel):
    """Handle cop calculation independent of the heat pump model"""

    def __init__(self, source_type: int = HeatPumpSourceType.AIR.value):
        self._source_type = source_type

    def _calc_cop_from_temps(
        self,
        source_temp_C: float,
        condenser_temp_C: float,
    ):
        delta_temp = condenser_temp_C - source_temp_C
        if self._source_type == HeatPumpSourceType.AIR.value:
            return 6.08 - 0.09 * delta_temp + 0.0005 * delta_temp**2
        if self._source_type == HeatPumpSourceType.GROUND.value:
            return 10.29 - 0.21 * delta_temp + 0.0012 * delta_temp**2
        assert False, "Source type not supported"

    def calc_cop(
        self,
        source_temp_C: float,
        condenser_temp_C: float,
        heat_demand_kW: Optional[float] = None,
    ) -> float:
        """COP model following https://www.nature.com/articles/s41597-019-0199-y"""
        return self._calc_cop_from_temps(source_temp_C, condenser_temp_C)

    def calc_q_from_p_kW(
        self,
        source_temp_C: float,
        condenser_temp_C: float,
        electrical_demand_kW: Optional[float] = None,
    ):
        return electrical_demand_kW * self._calc_cop_from_temps(source_temp_C, condenser_temp_C)


def cop_model_factory(
    model_type: COPModelType, source_type: int = HeatPumpSourceType.AIR.value
) -> BaseCOPModel:
    """Return the correct COP model."""
    if model_type == COPModelType.UNIVERSAL:
        return UniversalCOPModel(source_type)
    return IndividualCOPModel(model_type)
