from math import isclose

import numpy as np
import pytest

from gsy_e.models.strategy.energy_parameters.heatpump.cop_models.cop_models import (
    IndividualCOPModel,
    COPModelType,
)


class TestCopModels:

    @pytest.mark.parametrize(
        "model_type, min_heat, max_heat",
        [
            [COPModelType.ELCO_AEROTOP_S09_IR, 5, 18],
            [COPModelType.ELCO_AEROTOP_G07_14M, 5, 18],
            [COPModelType.HOVAL_ULTRASOURCE_B_COMFORT_C11, 4, 11],
            [COPModelType.AERMEC_NXP_0600_4L_HEAT, 140, 180],
            [COPModelType.AERMEC_NXP_0600_4L_COOL, 110, 160],
        ],
    )
    def test_if_forward_equals_backward(self, model_type, min_heat, max_heat):
        # pylint: disable=protected-access
        cop_model = IndividualCOPModel(model_type=model_type)
        source_temp = 11
        condenser_temp = 30
        for input_heat in np.linspace(min_heat, max_heat, 4):
            print(input_heat)
            power = cop_model._calc_power(source_temp, condenser_temp, input_heat)
            heat = cop_model.calc_q_from_p_kW(source_temp, condenser_temp, power)
            assert isclose(heat, input_heat), f"input_heat: {input_heat}"
