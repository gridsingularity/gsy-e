from random import randint
from unittest.mock import MagicMock

import pytest
from gsy_framework.constants_limits import GlobalConfig
from gsy_framework.read_user_profile import InputProfileTypes, convert_kW_to_kWh

import gsy_e.constants
from gsy_e.gsy_e_core.global_objects_singleton import global_objects
from gsy_e.models.strategy.strategy_profile import StrategyProfile


@pytest.fixture(name="db")
def profile_db_connection_fixture():
    """Sets up a fake connection to db with some prepopulated profile data."""
    gsy_e.constants.CONNECT_TO_PROFILES_DB = True
    db = MagicMock(_user_profiles={"UUID": {i: 5 for i in range(24)}})
    db.get_profile_from_db_buffer = lambda uuid: db._user_profiles[uuid]
    global_objects.profiles_handler.db = db
    yield db
    gsy_e.constants.CONNECT_TO_PROFILES_DB = False
    global_objects.profiles_handler.db = None


class TestEnergyProfile:
    """Tests for the EnergyProfile class."""

    @staticmethod
    def test_energy_profile_with_identity_input_profile():
        """Check input profile when no read from db is required and no input_energy_rate is set."""
        ep = StrategyProfile(
            input_profile={i: randint(15, 30) for i in range(24)},
            input_profile_uuid="UUID",
            input_energy_rate=None,
            profile_type=InputProfileTypes.IDENTITY
        )

        assert ep.input_profile_uuid is None
        assert ep.input_energy_rate is None
        assert ep.profile == {}

        ep.read_or_rotate_profiles()

        for time_slot, rate in ep.profile.items():
            assert ep.input_profile.get(time_slot.hour) == rate

    @staticmethod
    def test_energy_profile_with_identity_input_profile_rate():
        """Check input_energy_rate has priority over input_profile and input_profile_uuid."""
        ep = StrategyProfile(
            input_profile={i: randint(15, 30) for i in range(24)},
            input_profile_uuid="UUID",
            input_energy_rate=30,
            profile_type=InputProfileTypes.IDENTITY
        )

        assert ep.input_profile is None
        assert ep.input_profile_uuid is None
        assert ep.profile == {}

        ep.read_or_rotate_profiles()

        for _, rate in ep.profile.items():
            assert rate == 30

    @staticmethod
    def test_energy_profile_with_identity_input_profile_uuid(db):
        """Check input_profile_uuid has priority over input_profile_uuid and input_profile_rate."""
        ep = StrategyProfile(
            input_profile={i: randint(15, 30) for i in range(24)},
            input_profile_uuid="UUID",
            input_energy_rate=30,
            profile_type=InputProfileTypes.IDENTITY
        )

        assert ep.input_profile is None
        assert ep.input_energy_rate is None
        assert ep.profile == {}

        ep.read_or_rotate_profiles()

        for _, rate in ep.profile.items():
            assert rate == 5

    @staticmethod
    def test_energy_profile_with_power_input_profile():
        """Check input_profile when profile_type is set to InputProfileTypes.POWER_W."""
        ep = StrategyProfile(
            input_profile={i: randint(1000, 2000) for i in range(24)},
            input_profile_uuid="UUID",
            input_energy_rate=None,
            profile_type=InputProfileTypes.POWER_W
        )

        assert ep.input_profile_uuid is None
        assert ep.input_energy_rate is None
        assert ep.profile == {}

        ep.read_or_rotate_profiles()

        for time_slot, power in ep.profile.items():
            assert convert_kW_to_kWh(
                power_W=ep.input_profile.get(time_slot.hour) / 1000,
                slot_length=GlobalConfig.slot_length) == power

    @staticmethod
    def test_energy_profile_with_power_input_profile_rate():
        """Check input_profile_rate when profile_type is set to InputProfileTypes.POWER_W."""
        ep = StrategyProfile(
            input_profile={i: randint(15, 30) for i in range(24)},
            input_profile_uuid="UUID",
            input_energy_rate=3000,
            profile_type=InputProfileTypes.POWER_W
        )

        ep.read_or_rotate_profiles()
        for _, power in ep.profile.items():
            assert power == convert_kW_to_kWh(power_W=3, slot_length=GlobalConfig.slot_length)

    @staticmethod
    def test_energy_profile_reconfigure():
        """Check profile reconfigure works."""
        ep = StrategyProfile(
            input_profile={i: randint(15, 30) for i in range(24)},
            input_profile_uuid="UUID",
            input_energy_rate=3000,
            profile_type=InputProfileTypes.POWER_W
        )

        ep.read_or_rotate_profiles()
        last_profile = ep.profile
        for _, power in ep.profile.items():
            assert power == convert_kW_to_kWh(power_W=3, slot_length=GlobalConfig.slot_length)

        ep.input_energy_rate = 4000
        ep.read_or_rotate_profiles(reconfigure=True)
        assert last_profile != ep.profile
        for _, power in ep.profile.items():
            assert power == convert_kW_to_kWh(power_W=4, slot_length=GlobalConfig.slot_length)
