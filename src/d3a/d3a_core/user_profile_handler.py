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
from d3a_interface.constants_limits import TIME_ZONE
from d3a_interface.utils import generate_market_slot_list
from pendulum import instance, DateTime
from pony.orm import Database, Required, db_session, select
from pony.orm.core import Query


class ProfileDBConnectionHandler:
    """
    Handles connection to a postgres DB with pony ORM
    and the user profiles that are stored in the DB,
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
        self._profile_uuid_type_mapping = {}
        self._user_profiles = {}
        self._buffered_times = []
        self._current_timestamp = None

    def _update_current_time(self, timestamp: DateTime):
        self._current_timestamp = timestamp

    @staticmethod
    def convert_pendulum_to_datetime(time_stamp):
        return datetime.fromtimestamp(time_stamp.timestamp(), tz=pytz.UTC)

    @property
    def current_timestamp(self):
        return self._current_timestamp

    def connect(self):
        """ Establishes a connection to the d3a-profiles DB
        Requires a postgres DB server running

        """
        if d3a.constants.CONNECT_TO_PROFILES_DB:
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
                           if datapoint.profile_uuid in self._profile_uuid_type_mapping.keys()
                           and datapoint.time >= start_time and datapoint.time <= end_time)

        return selection

    @db_session
    def _populate_profile_uuid_type_mapping(self):
        """ Buffers a mapping between profile uuid and the type of the profile into
        self._profile_uuid_type_mapping which is currently used to keep track
        of the list of profile_uuids

        """
        profile_selection = select(
            (datapoint.profile_uuid, datapoint.profile_type)
            for datapoint in self.ConfigurationAreaProfileUuids
            if datapoint.configuration_uuid == d3a.constants.CONFIGURATION_ID)

        for profile_uuid, profile_type in profile_selection:
            self._profile_uuid_type_mapping[profile_uuid] = profile_type

    @db_session
    def _buffer_all_profiles(self):
        """ Loops over all profile uuids used in the setup and
        reads a new chunk of data from the DB

        """
        start_time, end_time = self._get_start_end_time()
        query_ret_val = self._get_profiles_from_db(self.convert_pendulum_to_datetime(start_time),
                                                   self.convert_pendulum_to_datetime(end_time))

        for profile_uuid in self._profile_uuid_type_mapping.keys():
            self._user_profiles[profile_uuid] = \
                {instance(data_point.time, TIME_ZONE): data_point.value
                 for data_point in query_ret_val if data_point.profile_uuid == profile_uuid}

    def _buffer_time_slots(self):
        """ Buffers a list of time_slots that are currently buffered in the user profiles.
        These are user to decide whether to rotate the buffer

        """
        first_profile_uuid = list(self._profile_uuid_type_mapping.keys())[0]
        time_stamps = self._user_profiles[first_profile_uuid].keys()
        self._buffered_times = list(time_stamps)

    def _get_start_end_time(self) -> (DateTime, DateTime):
        """ Gets the start and end time for the to be buffered profile.
        It uses generate_market_slot_list that takes into account the PROFILE_EXPANSION_DAYS

        Returns: tuple of timestamps

        """
        time_stamps = generate_market_slot_list(self.current_timestamp)
        return min(time_stamps), max(time_stamps)

    def buffer_profiles_from_db(self, current_timestamp: DateTime):
        """ Public method for buffering profiles and all other information from DB into memory

        Args:
            current_timestamp (Datetime): Current pendulum time stamp
                                          that is used to decide whether to buffer or not

        """
        self._update_current_time(current_timestamp)

        if not self._buffered_times or self.current_timestamp not in self._buffered_times:
            self._populate_profile_uuid_type_mapping()
            self._buffer_all_profiles()
            self._buffer_time_slots()

    def get_profile_from_db_buffer(self, profile_uuid: str) -> Dict:
        """ Wrapper for acquiring a user profile for a specific profile_uuid

        Args:
            profile_uuid (str):

        Returns:
            user profile for dictionary

        """
        return self._user_profiles[profile_uuid]
