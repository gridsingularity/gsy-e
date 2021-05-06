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
import logging
import os
from datetime import datetime
import pytz

import d3a.constants
from d3a_interface.constants_limits import TIME_ZONE
from d3a_interface.utils import generate_market_slot_list
from pendulum import instance, DateTime
from pony.orm import Database, Required, db_session, select


class ProfileDBConnectionHandler:
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
        self._user_profiles = {}  # Dict(profile_uuid, profile)
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
        if d3a.constants.CONNECT_TO_PROFILES_DB:
            self._db.bind(provider='postgres',
                          user=os.environ.get("PROFILE_DB_USER", "d3a_profiles"),
                          password=os.environ.get("PROFILE_DB_PASSWORD", ""),
                          host=os.environ.get("PROFILE_DB_HOST", "localhost"),
                          port=os.environ.get("PROFILE_DB_PORT", "5432"),
                          database=os.environ.get("PROFILE_DB_NAME", "d3a_profiles"))

            self._db.generate_mapping(check_tables=True)

    @db_session
    def _get_profile(self, profile_uuid, start_time=None, end_time=None):
        if start_time and end_time:
            selection = select(datapoint for datapoint in self.ProfileTimeSeries
                               if datapoint.profile_uuid == profile_uuid
                               and datapoint.time >= start_time and datapoint.time <= end_time)
        else:
            selection = self.ProfileTimeSeries.select(profile_uuid=profile_uuid)

        if len(selection) == 0:
            logging.error(f"No profile found for (uuid:{profile_uuid}, start_time:{start_time}, "
                          f"end_time: {end_time}).")

        return selection

    @staticmethod
    def _convert_db_profile_into_dict(db_selection):
        if len(db_selection) > 0:
            return {instance(data_point.time, TIME_ZONE): data_point.value
                    for data_point in db_selection}
        else:
            return {}

    @db_session
    def _get_profile_from_db(self, profile_uuid, start_time=None, end_time=None):
        return self._convert_db_profile_into_dict(
            self._get_profile(profile_uuid,
                              start_time=self.convert_pendulum_to_datetime(start_time),
                              end_time=self.convert_pendulum_to_datetime(end_time)))

    @db_session
    def _populate_profile_uuid_type_mapping(self):
        """
        The profile type is not used yet, but might be handy in the future
        :return:
        """
        profile_selection = select(
            (datapoint.profile_uuid, datapoint.profile_type)
            for datapoint in self.ConfigurationAreaProfileUuids
            if datapoint.configuration_uuid == d3a.constants.CONFIGURATION_ID)

        for profile_uuid, profile_type in profile_selection:
            self._profile_uuid_type_mapping[profile_uuid] = profile_type

    def _buffer_all_profiles(self):
        start_time, end_time = self._get_start_end_time()
        for profile_uuid in self._profile_uuid_type_mapping.keys():
            self._user_profiles[profile_uuid] = \
                self._get_profile_from_db(profile_uuid, start_time, end_time)

    def _buffer_time_slots(self):
        first_profile_uuid = list(self._profile_uuid_type_mapping.keys())[0]
        time_stamps = self._user_profiles[first_profile_uuid].keys()
        self._buffered_times = list(time_stamps)

    def _get_start_end_time(self):
        time_stamps = generate_market_slot_list(self.current_timestamp)
        return min(time_stamps), max(time_stamps)

    def buffer_profiles_from_db(self, current_timestamp):
        self._update_current_time(current_timestamp)

        if not self._buffered_times or self.current_timestamp not in self._buffered_times:
            self._populate_profile_uuid_type_mapping()
            self._buffer_all_profiles()
            self._buffer_time_slots()

    def get_profile_from_db_buffer(self, profile_uuid):
        return self._user_profiles[profile_uuid]
