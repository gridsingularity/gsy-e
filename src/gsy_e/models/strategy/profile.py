from gsy_framework.read_user_profile import InputProfileTypes

import gsy_e.constants
from gsy_e.gsy_e_core.global_objects_singleton import global_objects


class EnergyProfile:
    """Manage reading/rotating energy profile of an asset."""
    def __init__(self, input_profile, input_profile_uuid):
        self.input_profile = input_profile
        self.input_profile_uuid = input_profile_uuid

        # ignore input_profile if profile should be fetched from db.
        if self.should_read_profile_from_db(self.input_profile_uuid):
            self.input_profile = None

        self.profile = None

    @staticmethod
    def should_read_profile_from_db(profile_uuid) -> bool:
        """Boolean return if profile to be read from DB."""
        return profile_uuid is not None and gsy_e.constants.CONNECT_TO_PROFILES_DB

    @property
    def has_profile(self) -> bool:
        """Checks if the asset has a predefined profile."""
        return self.input_profile or self.input_profile_uuid

    def read_or_rotate_profiles(
            self, reconfigure=False,
            profile_type: InputProfileTypes = InputProfileTypes.POWER):
        """Rotate current profile or read and preprocess profile from source."""
        if not self.profile or reconfigure:
            profile = self.input_profile
        else:
            profile = self.profile

        self.profile = global_objects.profiles_handler.rotate_profile(
            profile_type=profile_type,
            profile=profile,
            profile_uuid=self.input_profile_uuid)
