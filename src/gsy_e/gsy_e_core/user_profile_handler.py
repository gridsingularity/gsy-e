"""
Copyright 2018 Grid Singularity
This file is part of Grid Singularity Exchange.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
import os
import uuid
from datetime import datetime
from typing import Dict, TYPE_CHECKING, List, Optional

import pytz
from gsy_framework.constants_limits import GlobalConfig
from gsy_framework.read_user_profile import read_arbitrary_profile, InputProfileTypes
from gsy_framework.utils import generate_market_slot_list
from pendulum import DateTime, instance, duration
from pony.orm import Database, Required, db_session, select
from pony.orm.core import Query

import gsy_e.constants
from gsy_e.gsy_e_core.util import should_read_profile_from_db

if TYPE_CHECKING:
    from gsy_e.models.area import Area


class ProfileDBConnectionException(Exception):
    """Exception that is raised inside ProfileDBConnectionHandler."""


PROFILE_UUID_NAMES = [
    "daily_load_profile_uuid",
    "power_profile_uuid",
    "energy_rate_profile_uuid",
    "smart_meter_profile_uuid",
    "buying_rate_profile_uuid",
    "consumption_kWh_profile_uuid",
    "external_temp_C_profile_uuid"
]


class ProfileDBConnectionHandler:
    """
    Handles connection and interaction with the user-profiles postgres DB via pony ORM
    """
    _db = Database()

    class Profile_Database_ProfileTimeSeries(_db.Entity):
        """Model for the profile timeseries data"""
        profile_uuid = Required(uuid.UUID)
        time = Required(datetime)
        value = Required(float)

    class Profile_Database_ConfigurationAreaProfileUuids(_db.Entity):
        """Model for the information associated with each profile"""
        configuration_uuid = Required(uuid.UUID)
        area_uuid = Required(uuid.UUID)
        profile_uuid = Required(uuid.UUID)
        profile_type = Required(int)  # values of InputProfileTypes

    def __init__(self):
        self._user_profiles: Dict[uuid.UUID, Dict[DateTime, float]] = {}
        self._profile_types: Dict[uuid.UUID, InputProfileTypes] = {}
        self._buffered_times: List[DateTime] = []
        self._profile_uuids: Optional[List[uuid.UUID]] = []

    @staticmethod
    def _convert_pendulum_to_datetime(time_stamp):
        return datetime.fromtimestamp(time_stamp.timestamp(), tz=pytz.UTC)

    @staticmethod
    def _strip_timezone_and_create_pendulum_instance_from_datetime(
            time_stamp: datetime) -> DateTime:
        return instance(time_stamp).in_timezone("UTC")

    def connect(self):
        """ Establishes a connection to the gsy_e-profiles DB
        Requires a postgres DB server running

        """
        if self._db.provider is not None:
            # DB already connected.
            return
        self._db.bind(provider="postgres",
                      user=os.environ.get("PROFILE_DB_USER", "d3a_web"),
                      password=os.environ.get("PROFILE_DB_PASSWORD", "d3a_web"),
                      host=os.environ.get("PROFILE_DB_HOST", "localhost"),
                      port=os.environ.get("PROFILE_DB_PORT", "5432"),
                      database=os.environ.get("PROFILE_DB_NAME", "d3a_web"))

        self._db.generate_mapping(check_tables=True)

    @db_session
    def get_first_week_from_profile(self, profile_uuid, current_timestamp) -> dict:
        """ Performs query to database and get the first week from a profile with the specified
            profile uuid. Current timestamp is used in order to rebase the start of the profile
            to the requested time from the simulation (e.g. if a profile contains values from
            before the simulation, the timestamps of these values will be moved to sync with
            the current_timestamp)

        Args:
            profile_uuid (UUID): uuid of the profile that we request the weekly data
            current_timestamp (datetime): timestamp that the profile timestamps will be moved to

        Returns: A dict with the timestamps of the adapted weekly profile as keys, and the profile
                 values as dict values.

        """
        if not isinstance(profile_uuid, uuid.UUID):
            profile_uuid = uuid.UUID(profile_uuid)
        first_datapoint = select(
            datapoint for datapoint in self.Profile_Database_ProfileTimeSeries
            if datapoint.profile_uuid == profile_uuid
        ).order_by(lambda d: d.time).limit(1)
        if len(first_datapoint) == 0:
            raise ProfileDBConnectionException(
                f"Profile in DB is empty for profile with uuid {profile_uuid}")
        first_datapoint_time = first_datapoint[0].time

        datapoints = list(select(
            datapoint for datapoint in self.Profile_Database_ProfileTimeSeries
            if datapoint.profile_uuid == profile_uuid
            and datapoint.time >= first_datapoint_time
            and datapoint.time <= first_datapoint_time + duration(days=7)
        ))
        diff_current_to_db_time = (
            current_timestamp -
            self._strip_timezone_and_create_pendulum_instance_from_datetime(datapoints[0].time)
        )
        return {
            self._strip_timezone_and_create_pendulum_instance_from_datetime(
                datapoint.time) + diff_current_to_db_time: datapoint.value
            for datapoint in datapoints
        }

    @db_session
    def _get_profiles_from_db(self, start_time: datetime, end_time: datetime) -> Query:
        """ Performs query to database and get chunks of profiles for all profiles that correspond
        to this simulation (that are buffered in self._profile_uuid_type_mapping)

        Args:
            start_time (datetime): first timestamp of the queried profile chunks (TZ unaware)
            end_time (datetime): last timestamp of the queried profile chunks (TZ unaware)

        Returns: A pony orm selection of the queried data

        """
        selection = select(
            datapoint for datapoint in self.Profile_Database_ProfileTimeSeries
            if datapoint.profile_uuid in self._profile_uuids
            and datapoint.time >= start_time and datapoint.time <= end_time
        )
        return selection

    @db_session
    def _get_profile_uuids_from_db(self):
        profile_selection = select(
            datapoint.profile_uuid
            for datapoint in self.Profile_Database_ConfigurationAreaProfileUuids
            if datapoint.configuration_uuid == uuid.UUID(gsy_e.constants.CONFIGURATION_ID))
        return list(profile_selection)

    def _buffer_profile_uuid_list(self, uuids_used_in_setup: List) -> None:
        """ Buffers list of the profile_uuids that correspond to this simulation into
        self._profile_uuids"""
        db_profile_uuids = self._get_profile_uuids_from_db()

        for used_profile_uuid in uuids_used_in_setup:
            if used_profile_uuid not in db_profile_uuids:
                raise ProfileDBConnectionException(
                    f"Did not find profile with uuid {str(used_profile_uuid)} in DB.")
        self._profile_uuids = list(uuids_used_in_setup)

    @db_session
    def buffer_profile_types(self):
        """
        Buffers profile types for the profiles of this simulation.
        """
        profile_selection = select(
            (datapoint.profile_uuid, datapoint.profile_type)
            for datapoint in self.Profile_Database_ConfigurationAreaProfileUuids
            if datapoint.configuration_uuid == uuid.UUID(gsy_e.constants.CONFIGURATION_ID))

        for profile in profile_selection:
            self._profile_types[profile[0]] = InputProfileTypes(profile[1])

    @db_session
    def _buffer_all_profiles(self, current_timestamp: DateTime):
        """ Loops over all profile uuids used in the setup and
        reads a new chunk of data from the DB

        Args:
            current_timestamp (Datetime): Current pendulum time stamp
        """
        start_time, end_time = self._get_start_end_time(current_timestamp)
        query_ret_val = self._get_profiles_from_db(self._convert_pendulum_to_datetime(start_time),
                                                   self._convert_pendulum_to_datetime(end_time))

        for profile_uuid in self._profile_uuids:
            self._user_profiles[profile_uuid] = {
                self._strip_timezone_and_create_pendulum_instance_from_datetime(
                    data_point.time): data_point.value
                for data_point in query_ret_val if data_point.profile_uuid == profile_uuid
            }

        for profile_uuid, profile_timeseries in self._user_profiles.items():
            if not profile_timeseries:
                self._user_profiles[profile_uuid] = self.get_first_week_from_profile(
                    profile_uuid, current_timestamp)

    def _buffer_time_slots(self):
        """ Buffers a list of time_slots that are currently buffered in the user profiles.
        These are user to decide whether to rotate the buffer

        """
        if len(self._profile_uuids) > 0:
            time_stamps = self._user_profiles[self._profile_uuids[0]].keys()
            self._buffered_times = list(time_stamps)
        else:
            self._buffered_times = []

    @staticmethod
    def _get_start_end_time(current_timestamp: DateTime) -> (DateTime, DateTime):
        """ Gets the start and end time for the to be buffered profile.
        It uses generate_market_slot_list that takes into account the PROFILE_EXPANSION_DAYS

        Returns: tuple of timestamps

        """
        time_stamps = generate_market_slot_list(current_timestamp)
        return min(time_stamps), max(time_stamps)

    def _should_buffer_profiles(self, current_timestamp: DateTime):
        return (self._profile_uuids is None or
                (not self._buffered_times or (current_timestamp not in self._buffered_times)))

    def buffer_profiles_from_db(self, current_timestamp: DateTime, uuids_used_in_setup: List):
        """ Public method for buffering profiles and all other information from DB into memory

        Args:
            current_timestamp (Datetime): Current pendulum time stamp
                                          that is used to decide whether to buffer or not

        """
        if self._should_buffer_profiles(current_timestamp):
            self.buffer_profile_types()
            self._buffer_profile_uuid_list(uuids_used_in_setup)
            self._buffer_all_profiles(current_timestamp)
            self._buffer_time_slots()

    def get_profile_type_from_db_buffer(self, profile_uuid: str) -> InputProfileTypes:
        """Read type of profile."""
        return self._profile_types[uuid.UUID(profile_uuid)]

    def get_profile_from_db_buffer(self, profile_uuid: str) -> Dict:
        """ Wrapper for acquiring a user profile for a specific profile_uuid

        Args:
            profile_uuid (str):

        Returns:
            user profile for dictionary

        """
        return self._user_profiles[uuid.UUID(profile_uuid)]


class ProfilesHandler:
    """
    Handles profiles rotation of all profiles (stored in DB and in memory)
    """
    def __init__(self):
        self.db = None
        self._current_timestamp = GlobalConfig.start_date
        self._start_date = GlobalConfig.start_date
        self._duration = GlobalConfig.sim_duration

    def activate(self):
        """Connect to DB, update current timestamp and get the first chunk of data from the DB"""
        self._connect_to_db()
        self._update_current_time(GlobalConfig.start_date)
        if self.db:
            self.db.buffer_profile_types()

    def _connect_to_db(self):
        if gsy_e.constants.CONNECT_TO_PROFILES_DB:
            self.db = ProfileDBConnectionHandler()
            self.db.connect()

    @property
    def current_timestamp(self):
        """Get the current timestamp of the simulation"""
        return self._current_timestamp

    def _update_current_time(self, timestamp: DateTime):
        self._current_timestamp = timestamp

    def update_time_and_buffer_profiles(self, timestamp: DateTime, area: "Area") -> None:
        """ Update current timestamp and get the first chunk of data from the DB"""
        self._update_current_time(timestamp)
        if self.db:
            uuids_used_in_setup = self._get_profile_uuids_from_setup(area)
            self.db.buffer_profiles_from_db(timestamp, uuids_used_in_setup)

    def _read_new_datapoints_from_buffer_or_rotate_profile(
            self, profile, profile_uuid, profile_type):
        if should_read_profile_from_db(profile_uuid):
            db_profile = self.db.get_profile_from_db_buffer(profile_uuid)
            if not db_profile:
                db_profile = self.db.get_first_week_from_profile(
                    profile_uuid, self.current_timestamp)
            return read_arbitrary_profile(profile_type,
                                          db_profile,
                                          current_timestamp=self.current_timestamp)
        return read_arbitrary_profile(profile_type,
                                      profile,
                                      current_timestamp=self.current_timestamp)

    def rotate_profile(self, profile_type: InputProfileTypes,
                       profile,
                       profile_uuid: str = None) -> Dict[DateTime, float]:
        """ Reads a new chunk of profile if the buffer does not contain the current time stamp
        Profile chunks are either generated from single values, input daily profiles or profiles
        that are read from the DB

        Args:
            profile_type (InputProfileTypes): Type of the profile
            profile (any of str, dict, float): Any arbitrary input
                                               (same input as for read_arbitrary_profile)
            profile_uuid (str): optional, if set the profiles is read from the DB

        Returns: Profile chunk as dictionary

        """
        if profile_uuid is None and self.should_create_profile(profile):
            return read_arbitrary_profile(profile_type,
                                          profile, current_timestamp=self.current_timestamp)
        if self.time_to_rotate_profile(profile):
            return self._read_new_datapoints_from_buffer_or_rotate_profile(
                profile, profile_uuid, profile_type)

        return profile

    def time_to_rotate_profile(self, profile):
        """ Checks if current time_stamp is part of the populated profile"""
        return profile is None or self.current_timestamp not in profile.keys()

    def should_create_profile(self, profile):
        """ Checks if profile is already a populated Dict[Datetime, float] dict
         or if it is an input value (str, int, dict)
        """
        return (profile is not None and
                (not isinstance(profile, dict) or self.current_timestamp not in profile.keys()))

    def get_profile_type(self, profile_uuid: str) -> InputProfileTypes:
        """Read the profile type from a profile with the specified UUID."""
        return self.db.get_profile_type_from_db_buffer(profile_uuid)

    def _get_profile_uuids_from_setup(self, area: "Area") -> List:
        profile_uuids = []
        for profile_uuid_name in PROFILE_UUID_NAMES:
            profile_uuid = getattr(area.strategy, profile_uuid_name, None)
            if profile_uuid:
                profile_uuids.append(uuid.UUID(profile_uuid))

        if area.children:
            for child in area.children:
                profile_uuids.extend(self._get_profile_uuids_from_setup(child))

        return profile_uuids
