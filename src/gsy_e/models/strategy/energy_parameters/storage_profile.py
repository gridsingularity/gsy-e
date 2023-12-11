from typing import Dict, Union

from gsy_e.models.strategy.profile import EnergyProfile


class StorageProfileEnergyParameters:
    """Handle energy parameters of the StorageProfile strategy"""

    def __init__(
            self, storage_profile: Union[str, Dict[int, float], Dict[str, float]] = None,
            storage_profile_uuid: str = None):
        """Main input is the charge and discharge profile (storage profile) where positive values
        represent consuming / charging and negative values represent producing / discharging"""

        self.energy_profile = EnergyProfile(storage_profile, storage_profile_uuid)

    def serialize(self):
        """Serialize class parameters."""
        return {
            "storage_profile": self.energy_profile.input_profile,
            "storage_profile_uuid": self.energy_profile.input_profile_uuid
        }

    def market_cycle(self):
        """Perform actions on market cycle event."""
        self.energy_profile.read_or_rotate_profiles()
