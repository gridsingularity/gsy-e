import uuid
from unittest.mock import MagicMock, patch, Mock

from gsy_e.models.area import CoefficientArea
from gsy_e.models.strategy.profile import EnergyProfile
from gsy_e.models.strategy.scm.pv import SCMPVUserProfile, PVUserProfileEnergyParameters
from gsy_e.models.strategy.scm.load import SCMLoadProfileStrategy, DefinedLoadEnergyParameters

class TestSCMPVStrategies:
    # pylint: disable=protected-access
    @staticmethod
    def test_scm_pv_user_profile_strategy_updates_energy_forecast():
        pv = SCMPVUserProfile()
        area = CoefficientArea(name="pv", strategy=pv)
        pv.owner = Mock()
        with patch("gsy_e.models.strategy.scm.pv.PVUserProfileEnergyParameters"):
            pv.activate(area)
        pv._energy_params.read_predefined_profile_for_pv.assert_called_once()
        pv._energy_params.set_produced_energy_forecast_in_state.assert_called_once()

        pv._energy_params.reset_mock()
        pv.market_cycle(area)
        pv._energy_params.read_predefined_profile_for_pv.assert_called_once()
        pv._energy_params.set_produced_energy_forecast_in_state.assert_called_once()


class TestSCMLoadStrategies:

    @staticmethod
    def test_scm_load_profile_strategy_updates_energy_forecast():
        # pylint: disable=protected-access
        load = SCMLoadProfileStrategy()
        area = CoefficientArea(name="load", strategy=load)
        load.owner = Mock()
        with patch("gsy_e.models.strategy.scm.load.DefinedLoadEnergyParameters"):
            load.activate(area)

        load._energy_params.event_activate_energy.assert_called_once()

        load._energy_params.reset_mock()
        load.market_cycle(area)
        load._energy_params.energy_profile.read_or_rotate_profiles.assert_called_once()
        load._energy_params.update_energy_requirement.assert_called_once()
