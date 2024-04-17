from typing import Dict

from pendulum import DateTime
from gsy_framework.read_user_profile import InputProfileTypes
from gsy_framework.constants_limits import GlobalConfig

from gsy_e.models.strategy.energy_parameters.load import DefinedLoadEnergyParameters
from gsy_e.models.strategy.scm.load import SCMLoadProfileStrategy


class ScmHeatPumpEnergyParameters(DefinedLoadEnergyParameters):
    """
    Heat Pump Energy Parameters for the ScmHeatPumpStrategy
    Only needed in order to only allow energy profiles
    """

    def __init__(self, consumption_kWh_profile=None,
                 consumption_kWh_profile_uuid: str = None):
        super().__init__(consumption_kWh_profile, consumption_kWh_profile_uuid)

        self.energy_profile.profile_type = InputProfileTypes.ENERGY_KWH

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

    def __init__(self, consumption_kWh_profile=None,
                 consumption_kWh_profile_uuid: str = None):
        # pylint: disable= super-init-not-called
        """super() should not be called"""
        self._energy_params = ScmHeatPumpEnergyParameters(
            consumption_kWh_profile, consumption_kWh_profile_uuid)

        # needed for profile_handler
        self.consumption_kWh_profile_uuid = consumption_kWh_profile_uuid

    @staticmethod
    def deserialize_args(constructor_args: Dict) -> Dict:
        if not GlobalConfig.is_canary_network():
            return constructor_args
        # move measurement_uuid into forecast uuid because this is only used in SCM
        measurement_uuid = constructor_args.get("consumption_kWh_measurement_uuid")
        if measurement_uuid:
            constructor_args["consumption_kWh_profile_uuid"] = measurement_uuid
        return constructor_args
