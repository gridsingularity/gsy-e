from gsy_framework.read_user_profile import InputProfileTypes

from gsy_e.gsy_e_core.global_objects_singleton import global_objects
from gsy_e.gsy_e_core.util import should_read_profile_from_db


class EnergyProfile:
    """Manage reading/rotating energy profile of an asset."""
    def __init__(
            self, input_profile=None, input_profile_uuid=None,
            input_energy_rate=None, profile_type: InputProfileTypes = None):

        self.input_profile = input_profile
        self.input_profile_uuid = input_profile_uuid
        self.input_energy_rate = input_energy_rate

        if should_read_profile_from_db(self.input_profile_uuid):
            self.input_profile = None
            self.input_energy_rate = None
        elif input_energy_rate is not None:
            self.input_profile = None
            self.input_profile_uuid = None
        else:
            self.input_profile_uuid = None
            self.input_energy_rate = None

        self.profile = {}

        self.profile_type = profile_type

    def _read_input_profile_type(self):
        """Read input profile type. Has to be called after initialization."""
        if self.input_profile_uuid:
            self.profile_type = global_objects.profiles_handler.get_profile_type(
                self.input_profile_uuid)
        elif self.input_energy_rate is not None:
            self.profile_type = InputProfileTypes.IDENTITY
        else:
            self.profile_type = InputProfileTypes.POWER_W

    def read_or_rotate_profiles(self, reconfigure=False):
        """Rotate current profile or read and preprocess profile from source."""
        if self.profile_type is None:
            self._read_input_profile_type()

        if not self.profile or reconfigure:
            profile = (self.input_energy_rate
                       if self.input_energy_rate is not None
                       else self.input_profile)
        else:
            profile = self.profile

        self.profile = global_objects.profiles_handler.rotate_profile(
            profile_type=self.profile_type,
            profile=profile,
            profile_uuid=self.input_profile_uuid)
