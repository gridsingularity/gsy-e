from abc import abstractmethod, ABC
import logging
from functools import cache
from pendulum import DateTime

from gsy_framework.read_user_profile import InputProfileTypes
from gsy_framework.constants_limits import GlobalConfig
from gsy_framework.utils import get_from_profile_same_weekday_and_time
from gsy_framework.validators.profile_validator import ProfileValidator

from gsy_e.gsy_e_core.global_objects_singleton import global_objects
from gsy_e.gsy_e_core.util import should_read_profile_from_db
from gsy_e.models.strategy.utils import is_scm_simulation

log = logging.getLogger(__name__)


class StrategyProfileBase(ABC):
    """Base class for Profiles"""

    def __init__(self):
        self.profile = {}
        self.profile_type = None
        self.input_profile_uuid = None
        self.input_energy_rate = None
        self.input_profile = None

    @abstractmethod
    def _read_input_profile_type(self):
        """Read input profile type. Has to be called after initialization."""

    @abstractmethod
    def read_or_rotate_profiles(self, reconfigure=False):
        """Rotate current profile or read and preprocess profile from source."""

    def get_value(self, _time_slot: DateTime):
        """Return value for specific time_slot."""
        return 0


class EmptyProfile(StrategyProfileBase):
    """Empty profile class"""

    def __init__(self, profile_type: InputProfileTypes = None):
        super().__init__()
        self.profile = {}
        self.profile_type = profile_type

    def _read_input_profile_type(self):
        pass

    def read_or_rotate_profiles(self, reconfigure=False):
        pass


class StrategyProfile(StrategyProfileBase):
    """Manage reading/rotating energy profile of an asset."""

    def __init__(
        self,
        input_profile=None,
        input_profile_uuid=None,
        input_energy_rate=None,
        profile_type: InputProfileTypes = None,
    ):
        # pylint: disable=super-init-not-called
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

    def get_value(self, time_slot: DateTime) -> float:
        if not self.profile:
            return 0
        if time_slot in self.profile:
            return self.profile[time_slot]
        if GlobalConfig.is_canary_network() or is_scm_simulation():
            value = get_from_profile_same_weekday_and_time(self.profile, time_slot)
            if value is None:
                log.error(
                    "Value for time_slot %s could not be found in profile %s in "
                    "Canary Network, returning 0",
                    time_slot,
                    self.input_profile_uuid,
                )
                return 0
            return value
        log.error(
            "Value for time_slot %s could not be found in profile %s.",
            time_slot,
            self.input_profile_uuid,
        )
        return 0

    def _read_input_profile_type(self):
        if self.input_profile_uuid:
            self.profile_type = global_objects.profiles_handler.get_profile_type(
                self.input_profile_uuid
            )
        elif self.input_energy_rate is not None:
            self.profile_type = InputProfileTypes.IDENTITY
        else:
            self.profile_type = InputProfileTypes.POWER_W

    def _add_last_slot_value_to_new_profile_rotation(self, new_profile_chunk: dict):
        if new_profile_chunk is None:
            return self.profile

        if not self.profile:
            return new_profile_chunk

        last_timestamp = list(self.profile.keys())[-1]
        last_profile_element = {last_timestamp: self.profile[last_timestamp]}
        if last_timestamp in new_profile_chunk:
            # case when the profile was already populated but rotation was triggered again
            return new_profile_chunk
        return {**last_profile_element, **new_profile_chunk}

    def read_or_rotate_profiles(self, reconfigure=False):
        if self.profile_type is None:
            self._read_input_profile_type()

        if not self.profile or reconfigure:
            profile = (
                self.input_energy_rate
                if self.input_energy_rate is not None
                else self.input_profile
            )
        else:
            profile = self.profile

        new_profile_chunk = global_objects.profiles_handler.rotate_profile(
            profile_type=self.profile_type,
            profile=profile,
            profile_uuid=self.input_profile_uuid,
            input_profile_path=self.input_profile,
        )

        self.profile = self._add_last_slot_value_to_new_profile_rotation(new_profile_chunk)
        self._validate_and_log_profile()

    def _validate_and_log_profile(self):
        try:
            ProfileValidator(self.profile, slot_length=GlobalConfig.slot_length).validate()
        except AssertionError as exc:
            self._log_once(
                f"Validation of profile time slot fails for profile {self.input_profile_uuid} "
                f"({str(exc)})"
            )

    @staticmethod
    @cache
    def _log_once(msg: str):
        log.error(msg)


def profile_factory(
    input_profile=None,
    input_profile_uuid=None,
    input_energy_rate=None,
    profile_type: InputProfileTypes = None,
) -> StrategyProfileBase:
    """Return correct profile handling class for input parameters."""
    return (
        EmptyProfile(profile_type)
        if input_profile is None and input_profile_uuid is None and input_energy_rate is None
        else StrategyProfile(input_profile, input_profile_uuid, input_energy_rate, profile_type)
    )
