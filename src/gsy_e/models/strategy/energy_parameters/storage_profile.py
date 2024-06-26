from typing import Dict, Union

from gsy_framework.read_user_profile import InputProfileTypes

from gsy_e.models.strategy.strategy_profile import profile_factory
from gsy_e.models.strategy.state.base_states import DummyState


class StorageProfileEnergyParameters:
    """Handle energy parameters of the StorageProfile strategy"""

    def __init__(
            self, prosumption_kWh_profile: Union[str, Dict[int, float], Dict[str, float]] = None,
            prosumption_kWh_profile_uuid: str = None,
            prosumption_kWh_measurement_uuid: str = None):
        """Main input is the charge and discharge profile (storage profile) where positive values
        represent consuming / charging and negative values represent producing / discharging"""

        self.energy_profile = profile_factory(
            prosumption_kWh_profile,
            prosumption_kWh_profile_uuid,
            profile_type=InputProfileTypes.ENERGY_KWH)
        self.energy_measurement = profile_factory(
            None, prosumption_kWh_measurement_uuid,
            profile_type=InputProfileTypes.ENERGY_KWH)

        self.state = DummyState()

    def serialize(self):
        """Serialize class parameters."""
        return {
            "prosumption_kWh_profile": self.energy_profile.input_profile,
            "prosumption_kWh_profile_uuid": self.energy_profile.input_profile_uuid,
            "prosumption_kWh_measurement_uuid": self.energy_measurement.input_profile_uuid
        }

    def market_cycle(self):
        """Perform actions on market cycle event."""
        self.energy_profile.read_or_rotate_profiles()
        self.energy_measurement.read_or_rotate_profiles()
