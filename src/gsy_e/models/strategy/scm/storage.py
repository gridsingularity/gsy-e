from typing import Dict, Union

from pendulum import DateTime
from gsy_framework.constants_limits import GlobalConfig

from gsy_e.models.strategy.energy_parameters.storage_profile import StorageProfileEnergyParameters
from gsy_e.models.strategy.scm import SCMStrategy


class SCMStorageStrategy(SCMStrategy):
    """Storage SCM strategy."""

    def __init__(
            self, prosumption_kWh_profile: Union[str, Dict[int, float], Dict[str, float]] = None,
            prosumption_kWh_profile_uuid: str = None):

        self._energy_params = StorageProfileEnergyParameters(
            prosumption_kWh_profile, prosumption_kWh_profile_uuid)

        # needed for profile_handler
        self.prosumption_kWh_profile_uuid = prosumption_kWh_profile_uuid

    def serialize(self) -> Dict:
        """Serialize the strategy parameters."""
        return {**self._energy_params.serialize()}

    def activate(self, _area):
        """Overwriting Base method because there is nothing to be done when activating"""

    def market_cycle(self, _area):
        self._energy_params.market_cycle()

    def get_energy_to_sell_kWh(self, time_slot: DateTime) -> float:
        """Get the available energy for production for the specified time slot."""
        energy_value = self._energy_params.energy_profile.get_value(time_slot)
        return abs(energy_value) if energy_value and energy_value < 0 else 0

    def get_energy_to_buy_kWh(self, time_slot: DateTime) -> float:
        """Get the available energy for consumption for the specified time slot."""
        energy_value = self._energy_params.energy_profile.get_value(time_slot)
        return energy_value if energy_value and energy_value > 0 else 0

    @property
    def state(self):
        """Return empty state."""
        return self._energy_params.state

    @staticmethod
    def deserialize_args(constructor_args: Dict) -> Dict:
        if not GlobalConfig.is_canary_network():
            return constructor_args
        # move measurement_uuid into forecast uuid because this is only used in SCM
        measurement_uuid = constructor_args.get("prosumption_kWh_measurement_uuid")
        if measurement_uuid:
            constructor_args["prosumption_kWh_profile_uuid"] = measurement_uuid
        return constructor_args
