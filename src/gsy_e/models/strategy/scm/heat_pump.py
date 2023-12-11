from gsy_framework.read_user_profile import InputProfileTypes
from pendulum import DateTime

from gsy_e.models.strategy.energy_parameters.load import DefinedLoadEnergyParameters
from gsy_e.models.strategy.profile import EnergyProfile
from gsy_e.models.strategy.scm.load import SCMLoadProfileStrategy
from gsy_e.models.strategy.state import LoadState


class ScmHeatPumpEnergyParameters(DefinedLoadEnergyParameters):
    """
    Heat Pump Energy Parameters for the ScmHeatPumpStrategy
    Only needed in order to only allow energy profiles
    """

    def __init__(self, consumption_kWh_profile=None, consumption_kWh_profile_uuid: str = None):
        # pylint: disable= super-init-not-called
        """super() should not be called"""
        self.energy_profile = EnergyProfile(
            consumption_kWh_profile, consumption_kWh_profile_uuid,
            profile_type=InputProfileTypes.ENERGY_KWH)
        self.state = LoadState()

    def serialize(self):
        return {
            "consumption_kWh_profile": self.energy_profile.input_profile,
            "consumption_kWh_profile_uuid": self.energy_profile.input_profile_uuid
        }

    def reset(self, time_slot: DateTime, **kwargs) -> None:
        if kwargs.get("consumption_kWh_profile") is not None:
            self.energy_profile.input_profile = kwargs["consumption_kWh_profile"]
            self.energy_profile.read_or_rotate_profiles(reconfigure=True)


class ScmHeatPumpStrategy(SCMLoadProfileStrategy):
    """Heat Pump SCM strategy with power consumption dictated by a profile."""

    def __init__(self, consumption_kWh_profile=None, consumption_kWh_profile_uuid=None):
        # pylint: disable= super-init-not-called
        """super() should not be called"""
        self._energy_params = ScmHeatPumpEnergyParameters(
            consumption_kWh_profile, consumption_kWh_profile_uuid)
        self.consumption_kWh_profile_uuid = consumption_kWh_profile_uuid
