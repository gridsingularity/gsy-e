import uuid
from unittest.mock import Mock, MagicMock

import pytest
from pendulum import today
from pony.orm import Database

import gsy_e.constants
import gsy_e.gsy_e_core.user_profile_handler
from gsy_e.gsy_e_core.user_profile_handler import (ProfilesHandler, ProfileDBConnectionHandler,
                                                   ProfileDBConnectionException)
from gsy_e.models.area import Area
from gsy_e.models.strategy.predefined_load import DefinedLoadStrategy
from gsy_e.models.strategy.predefined_pv import PVUserProfileStrategy

CUSTOM_DATETIME = today()
PV_UUID = uuid.uuid4()
LOAD_UUID = uuid.uuid4()


@pytest.fixture(name="area_tree")
def area_tree_fixture():
    """Fixture for a simple area tree setup."""
    gsy_e.constants.CONFIGURATION_ID = str(uuid.uuid4())
    area = Area("root", children=[
        Area("Community", children=[
            Area("Load", strategy=DefinedLoadStrategy(
                daily_load_profile_uuid=str(LOAD_UUID))),
            Area("PV", strategy=PVUserProfileStrategy(
                power_profile_uuid=str(PV_UUID)))
        ])
    ])
    yield area
    gsy_e.constants.CONFIGURATION_ID = ""


class TestProfileDBConnectionHandler:
    # pylint: disable=protected-access, attribute-defined-outside-init

    def setup_method(self):
        self.profiles_handler = ProfilesHandler()
        profile_db = ProfileDBConnectionHandler()
        profile_db._db = MagicMock(autospec=Database)
        self.profiles_handler.db = profile_db

    def test_update_time_and_buffer_profiles_returns_error_for_missing_profiles(
            self, area_tree):
        self.profiles_handler._should_buffer_profiles = Mock(return_value=True)
        # only the load profile is saved in the DB
        self.profiles_handler.db._get_profile_uuids_from_db = Mock(
            return_value=[LOAD_UUID])
        self.profiles_handler.db.buffer_profile_types = Mock(return_value=None)
        with pytest.raises(ProfileDBConnectionException):
            self.profiles_handler.update_time_and_buffer_profiles(
                CUSTOM_DATETIME, area_tree)

    def test_update_time_and_buffer_profiles_only_buffers_used_profiles(
            self, area_tree):
        self.profiles_handler._should_buffer_profiles = Mock(return_value=True)
        # return one more profile uuid from the DB
        self.profiles_handler.db._get_profile_uuids_from_db = Mock(
            return_value=[LOAD_UUID, PV_UUID, uuid.uuid4()])
        self.profiles_handler.db.buffer_profile_types = Mock(return_value=None)
        self.profiles_handler.db._buffer_all_profiles = Mock(return_value=None)
        self.profiles_handler.db._buffer_time_slots = Mock(return_value=None)
        self.profiles_handler.update_time_and_buffer_profiles(
            CUSTOM_DATETIME, area_tree)
        assert set(self.profiles_handler.db._profile_uuids) == {LOAD_UUID, PV_UUID}
