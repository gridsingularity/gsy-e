from unittest.mock import MagicMock

from gsy_e.models.area import CoefficientArea
from gsy_e.models.strategy.strategy_profile import StrategyProfile
from gsy_e.models.strategy.scm.pv import SCMPVUserProfile, PVUserProfileEnergyParameters
from gsy_e.models.strategy.scm.load import SCMLoadProfileStrategy, DefinedLoadEnergyParameters


class TestSCMPVStrategies:
    # pylint: disable=protected-access
    @staticmethod
    def test_scm_pv_user_profile_strategy_updates_energy_forecast():
        energy_params = MagicMock(spec=PVUserProfileEnergyParameters)
        energy_params._state = MagicMock()
        pv = SCMPVUserProfile()
        area = CoefficientArea(name="pv", strategy=pv)

        pv._energy_params = energy_params
        pv.activate(area)
        energy_params.read_predefined_profile_for_pv.assert_called_once()
        energy_params.set_produced_energy_forecast_in_state.assert_called_once()

        energy_params.reset_mock()
        pv.market_cycle(area)
        energy_params.read_predefined_profile_for_pv.assert_called_once()
        energy_params.set_produced_energy_forecast_in_state.assert_called_once()


class TestSCMLoadStrategies:

    @staticmethod
    def test_scm_load_profile_strategy_updates_energy_forecast():
        # pylint: disable=protected-access
        energy_params = MagicMock(spec=DefinedLoadEnergyParameters)
        energy_params.energy_profile = MagicMock(spec=StrategyProfile)
        load = SCMLoadProfileStrategy()
        area = CoefficientArea(name="load", strategy=load)

        load._energy_params = energy_params
        load.activate(area)
        energy_params.event_activate_energy.assert_called_once()

        energy_params.reset_mock()
        load.market_cycle(area)
        energy_params.energy_profile.read_or_rotate_profiles.assert_called_once()
        energy_params.update_energy_requirement.assert_called_once()
