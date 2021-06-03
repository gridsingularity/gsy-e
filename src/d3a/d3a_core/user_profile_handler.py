"""
Copyright 2018 Grid Singularity
This file is part of D3A.

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
from datetime import datetime
from typing import Dict

import d3a.constants
import pytz
from d3a.d3a_core.util import should_read_profile_from_db
from d3a_interface.constants_limits import GlobalConfig
from d3a_interface.constants_limits import TIME_ZONE
from d3a_interface.read_user_profile import read_arbitrary_profile, InputProfileTypes
from d3a_interface.utils import generate_market_slot_list
from pendulum import DateTime
from pendulum import instance
from pony.orm import Database, Required, db_session, select
from pony.orm.core import Query


class ProfileDBConnectionHandler:
    """
    Handles connection and interaction with the user-profiles postgres DB via pony ORM
    """
    _db = Database()

    class ProfileTimeSeries(_db.Entity):
        profile_uuid = Required(str)
        time = Required(datetime)
        value = Required(float)

    class ConfigurationAreaProfileUuids(_db.Entity):
        configuration_uuid = Required(str)
        area_uuid = Required(str)
        profile_uuid = Required(str)
        profile_type = Required(int)  # values of InputProfileTypes

    def __init__(self):
        # self._profile_uuid_type_mapping = {}
        self._user_profiles = {}
        self._buffered_times = []
        self._profile_uuids = None

    @staticmethod
    def convert_pendulum_to_datetime(time_stamp):
        return datetime.fromtimestamp(time_stamp.timestamp(), tz=pytz.UTC)

    def connect(self):
        """ Establishes a connection to the d3a-profiles DB
        Requires a postgres DB server running

        """
        self._db.bind(provider='postgres',
                      user=os.environ.get("PROFILE_DB_USER", "d3a_profiles"),
                      password=os.environ.get("PROFILE_DB_PASSWORD", ""),
                      host=os.environ.get("PROFILE_DB_HOST", "localhost"),
                      port=os.environ.get("PROFILE_DB_PORT", "5432"),
                      database=os.environ.get("PROFILE_DB_NAME", "d3a_profiles"))

        self._db.generate_mapping(check_tables=True)

    @db_session
    def _get_profiles_from_db(self, start_time: datetime, end_time: datetime) -> Query:
        """ Performs query to database and get chunks of profiles for all profiles that correspond
        to this simulation (that are buffered in self._profile_uuid_type_mapping)

        Args:
            start_time (datetime): first timestamp of the queried profile chunks (TZ unaware)
            end_time (datetime): last timestamp of the queried profile chunks (TZ unaware)

        Returns: A pony orm selection of the queried data

        """
        selection = select(datapoint for datapoint in self.ProfileTimeSeries
                           if datapoint.profile_uuid in self._profile_uuids
                           and datapoint.time >= start_time and datapoint.time <= end_time)

        return selection

    @db_session
    def _buffer_profile_uuid_list(self):
        """ Buffers list of the profile_uuids that correspond to this simulation into
        self._profile_uuids"""
        profile_selection = select(
            datapoint.profile_uuid
            for datapoint in self.ConfigurationAreaProfileUuids
            if datapoint.configuration_uuid == d3a.constants.CONFIGURATION_ID)

        self._profile_uuids = list(profile_selection)

    @db_session
    def _buffer_all_profiles(self, current_timestamp: DateTime):
        """ Loops over all profile uuids used in the setup and
        reads a new chunk of data from the DB

        Args:
            current_timestamp (Datetime): Current pendulum time stamp
        """
        start_time, end_time = self._get_start_end_time(current_timestamp)
        query_ret_val = self._get_profiles_from_db(self.convert_pendulum_to_datetime(start_time),
                                                   self.convert_pendulum_to_datetime(end_time))

        for profile_uuid in self._profile_uuids:
            self._user_profiles[profile_uuid] = \
                {instance(data_point.time, TIME_ZONE): data_point.value
                 for data_point in query_ret_val if data_point.profile_uuid == profile_uuid}

    def _buffer_time_slots(self):
        """ Buffers a list of time_slots that are currently buffered in the user profiles.
        These are user to decide whether to rotate the buffer

        """
        if len(self._profile_uuids) > 0:
            time_stamps = self._user_profiles[self._profile_uuids[0]].keys()
            self._buffered_times = list(time_stamps)
        else:
            self._buffered_times = []

    def _get_start_end_time(self, current_timestamp: DateTime) -> (DateTime, DateTime):
        """ Gets the start and end time for the to be buffered profile.
        It uses generate_market_slot_list that takes into account the PROFILE_EXPANSION_DAYS

        Returns: tuple of timestamps

        """
        time_stamps = generate_market_slot_list(current_timestamp)
        return min(time_stamps), max(time_stamps)

    def should_buffer_profiles(self, current_timestamp: DateTime):
        return (self._profile_uuids is None or
                (not self._buffered_times or (current_timestamp not in self._buffered_times)))

    def buffer_profiles_from_db(self, current_timestamp: DateTime):
        """ Public method for buffering profiles and all other information from DB into memory

        Args:
            current_timestamp (Datetime): Current pendulum time stamp
                                          that is used to decide whether to buffer or not

        """
        if self.should_buffer_profiles(current_timestamp):
            self._buffer_profile_uuid_list()
            self._buffer_all_profiles(current_timestamp)
            self._buffer_time_slots()

    def get_profile_from_db_buffer(self, profile_uuid: str) -> Dict:
        """ Wrapper for acquiring a user profile for a specific profile_uuid

        Args:
            profile_uuid (str):

        Returns:
            user profile for dictionary

        """
        return self._user_profiles[profile_uuid]


class ProfilesHandler:
    """
    Handles profiles rotation of all profiles (stored in DB and in memory)
    """
    def __init__(self):
        self.db = None
        self._current_timestamp = GlobalConfig.start_date

    def activate(self):
        """Connect to DB, update current timestamp and get the first chunk of data from the DB"""
        self.connect_to_db()
        self.update_time_and_buffer_profiles(GlobalConfig.start_date)

    def connect_to_db(self):
        if d3a.constants.CONNECT_TO_PROFILES_DB:
            self.db = ProfileDBConnectionHandler()
            self.db.connect()

    @property
    def current_timestamp(self):
        return self._current_timestamp

    def _update_current_time(self, timestamp: DateTime):
        self._current_timestamp = timestamp

    def update_time_and_buffer_profiles(self, timestamp):
        """ Update current timestamp and get the first chunk of data from the DB"""
        self._update_current_time(timestamp)
        if self.db:
            self.db.buffer_profiles_from_db(timestamp)

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
        if self.should_create_profile(profile):
            return read_arbitrary_profile(profile_type,
                                          profile, current_timestamp=self.current_timestamp)
        elif self.time_to_rotate_profile(profile):
            if should_read_profile_from_db(profile_uuid):
                db_profile = \
                    self.db.get_profile_from_db_buffer(profile_uuid)
                return read_arbitrary_profile(profile_type,
                                              db_profile,
                                              current_timestamp=min(db_profile.keys()))
            else:
                return read_arbitrary_profile(profile_type,
                                              profile,
                                              current_timestamp=self.current_timestamp)

        else:
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
