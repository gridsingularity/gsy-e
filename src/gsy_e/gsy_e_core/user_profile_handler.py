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

from dataclasses import dataclass
import logging
import os
import uuid
from datetime import datetime
from typing import Dict, TYPE_CHECKING, List

import pytz
from gsy_framework.constants_limits import (
    GlobalConfig,
    ProfileUuidScenarioKeyNames,
    MeasurementProfileUuidScenarioKeyNames,
)
from gsy_framework.read_user_profile import read_arbitrary_profile, InputProfileTypes
from gsy_framework.utils import generate_market_slot_list
from pendulum import DateTime, instance, duration
from pony.orm import Database, Required, db_session, select, Optional
from pony.orm.core import Query

import gsy_e.constants
from gsy_e.gsy_e_core.util import should_read_profile_from_db

if TYPE_CHECKING:
    from gsy_e.models.area import Area

log = logging.getLogger(__name__)


class ProfileDBConnectionException(Exception):
    """Exception that is raised inside ProfileDBConnectionHandler."""


PROFILE_UUID_NAMES = [
    ProfileUuidScenarioKeyNames.LOAD_CONSUMPTION,
    ProfileUuidScenarioKeyNames.PV_PRODUCTION,
    ProfileUuidScenarioKeyNames.MARKET_MAKER_SELL_RATE,
    ProfileUuidScenarioKeyNames.SMART_METER_PROSUMPTION,
    ProfileUuidScenarioKeyNames.INFINITE_BUS_BUY_RATE,
    ProfileUuidScenarioKeyNames.HEATPUMP_CONSUMPTION,
    ProfileUuidScenarioKeyNames.HEATPUMP_SOURCE_TEMP,
    ProfileUuidScenarioKeyNames.SCM_STORAGE_PROSUMPTION,
    MeasurementProfileUuidScenarioKeyNames.HEATPUMP_CONSUMPTION,
    MeasurementProfileUuidScenarioKeyNames.HEATPUMP_SOURCE_TEMP,
    MeasurementProfileUuidScenarioKeyNames.SCM_STORAGE_PROSUMPTION,
    MeasurementProfileUuidScenarioKeyNames.LOAD_CONSUMPTION,
    MeasurementProfileUuidScenarioKeyNames.PV_PRODUCTION,
    MeasurementProfileUuidScenarioKeyNames.SMART_METER_PROSUMPTION,
]


@dataclass
class SCMFeesRatesProfileDatapoint:
    """Data point for profiles of energy rates and fees. Applicable only to SCM."""

    # pylint: disable=too-many-instance-attributes
    area_uuid: str
    feed_in_tariff: float
    utility_rate: float
    power_fee: float
    power_cargo_fee: float
    energy_fee: float
    energy_cargo_fee: float
    contracted_power_kw: float


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

    class Profile_Database_ProfileConfiguration(_db.Entity):
        """Bridge table between ConfigurationSettings and ProfileInformation"""

        config_uuid = Required(uuid.UUID)
        area_uuid = Required(uuid.UUID)
        profile_uuid = Required(uuid.UUID)

    class Profile_Database_ProfileInformation(_db.Entity):
        """Model for the information associated with each profile"""

        profile_uuid = Required(uuid.UUID)
        profile_type = Required(int)  # values of InputProfileTypes

    class Profile_Database_SCMCommunityMemberProfiles(_db.Entity):
        """Model for the SCM community member profile data"""

        config_uuid = Required(uuid.UUID)
        area_uuid = Required(uuid.UUID)
        time = Required(datetime)
        feed_in_tariff = Optional(float)
        utility_rate = Optional(float)
        power_fee = Optional(float)
        power_cargo_fee = Optional(float)
        energy_fee = Optional(float)
        energy_cargo_fee = Optional(float)
        contracted_power_kw = Optional(float)

    def __init__(self):
        self._user_profiles: Dict[uuid.UUID, Dict[DateTime, float]] = {}
        self._profile_types: Dict[uuid.UUID, InputProfileTypes] = {}
        self._buffered_times: List[DateTime] = []
        self._profile_uuids: List[uuid.UUID] | None = []

    @staticmethod
    def _convert_pendulum_to_datetime(time_stamp):
        return datetime.fromtimestamp(time_stamp.timestamp(), tz=pytz.UTC)

    @staticmethod
    def _strip_timezone_and_create_pendulum_instance_from_datetime(
        time_stamp: datetime,
    ) -> DateTime:
        return instance(time_stamp).in_timezone("UTC")

    def connect(self):
        """Establishes a connection to the gsy_e-profiles DB
        Requires a postgres DB server running

        """
        if self._db.provider is not None:
            # DB already connected.
            return
        self._db.bind(
            provider="postgres",
            user=os.environ.get("PROFILE_DB_USER", "d3a_web"),
            password=os.environ.get("PROFILE_DB_PASSWORD", "d3a_web"),
            host=os.environ.get("PROFILE_DB_HOST", "localhost"),
            port=os.environ.get("PROFILE_DB_PORT", "5432"),
            database=os.environ.get("PROFILE_DB_NAME", "d3a_web"),
        )

        self._db.generate_mapping(check_tables=True)

    @property
    def _buffer_duration(self) -> duration:
        # For canary networks, the DB should be checked for new data every market slot
        return GlobalConfig.slot_length if GlobalConfig.is_canary_network() else duration(days=7)

    @db_session
    def get_scm_data_profiles(self, timestamp: DateTime, config_uuid: str):
        """Retrieve the SCM-related profiles."""
        profile_datapoints = select(
            datapoint
            for datapoint in self.Profile_Database_SCMCommunityMemberProfiles
            if datapoint.config_uuid == uuid.UUID(config_uuid)
            and datapoint.time == self._convert_pendulum_to_datetime(timestamp)
        )
        return {
            str(datapoint.area_uuid): SCMFeesRatesProfileDatapoint(
                area_uuid=datapoint.area_uuid,
                feed_in_tariff=datapoint.feed_in_tariff,
                utility_rate=datapoint.utility_rate,
                power_fee=datapoint.power_fee,
                power_cargo_fee=datapoint.power_cargo_fee,
                energy_fee=datapoint.energy_fee,
                energy_cargo_fee=datapoint.energy_cargo_fee,
                contracted_power_kw=datapoint.contracted_power_kw,
            )
            for datapoint in profile_datapoints
        }

    @db_session
    def get_first_data_from_profile(self, profile_uuid, current_timestamp) -> dict:
        """Performs query to database and get the first data from a profile with the specified
            profile uuid. Current timestamp is used in order to rebase the start of the profile
            to the requested time from the simulation (e.g. if a profile contains values from
            before the simulation, the timestamps of these values will be moved to sync with
            the current_timestamp)

        Args:
            profile_uuid (UUID): uuid of the profile
            current_timestamp (datetime): timestamp that the profile timestamps will be moved to

        Returns: A dict with the timestamps of the profile as keys, and the profile
                 values as dict values.

        """
        if not isinstance(profile_uuid, uuid.UUID):
            profile_uuid = uuid.UUID(profile_uuid)

        if GlobalConfig.is_canary_network():
            first_datapoint = (
                select(
                    datapoint
                    for datapoint in self.Profile_Database_ProfileTimeSeries
                    if datapoint.profile_uuid == profile_uuid
                    and datapoint.time == self._convert_pendulum_to_datetime(current_timestamp)
                )
                .order_by(lambda d: d.time)
                .limit(1)
            )
            if len(first_datapoint) == 0:
                return {}
        else:
            first_datapoint = (
                select(
                    datapoint
                    for datapoint in self.Profile_Database_ProfileTimeSeries
                    if datapoint.profile_uuid == profile_uuid
                )
                .order_by(lambda d: d.time)
                .limit(1)
            )
            if len(first_datapoint) == 0:
                raise ProfileDBConnectionException(
                    f"Profile in DB is empty for profile with uuid {profile_uuid}"
                )
        first_datapoint_time = first_datapoint[0].time

        datapoints = list(
            select(
                datapoint
                for datapoint in self.Profile_Database_ProfileTimeSeries
                if datapoint.profile_uuid == profile_uuid
                and datapoint.time >= first_datapoint_time
                and datapoint.time <= first_datapoint_time + self._buffer_duration
            )
        )
        diff_current_to_db_time = (
            current_timestamp
            - self._strip_timezone_and_create_pendulum_instance_from_datetime(datapoints[0].time)
        )
        return {
            self._strip_timezone_and_create_pendulum_instance_from_datetime(datapoint.time)
            + diff_current_to_db_time: datapoint.value
            for datapoint in datapoints
        }

    @db_session
    def _get_profiles_from_db(self, start_time: datetime, end_time: datetime) -> Query:
        """Performs query to database and get chunks of profiles for all profiles that correspond
        to this simulation (that are buffered in self._profile_uuid_type_mapping)

        Args:
            start_time (datetime): first timestamp of the queried profile chunks (TZ unaware)
            end_time (datetime): last timestamp of the queried profile chunks (TZ unaware)

        Returns: A pony orm selection of the queried data

        """
        selection = select(
            datapoint
            for datapoint in self.Profile_Database_ProfileTimeSeries
            if datapoint.profile_uuid in self._profile_uuids
            and datapoint.time >= start_time
            and datapoint.time <= end_time
        )
        return selection

    @db_session
    def _get_profile_uuids_from_db(self):
        profile_selection = select(
            datapoint.profile_uuid
            for datapoint in self.Profile_Database_ProfileConfiguration
            if datapoint.config_uuid == uuid.UUID(gsy_e.constants.CONFIGURATION_ID)
        )
        return list(profile_selection)

    def _buffer_profile_uuid_list(self, uuids_used_in_setup: List) -> None:
        """Buffers list of the profile_uuids that correspond to this simulation into
        self._profile_uuids"""
        db_profile_uuids = self._get_profile_uuids_from_db()

        for used_profile_uuid in uuids_used_in_setup:
            if used_profile_uuid not in db_profile_uuids:
                raise ProfileDBConnectionException(
                    f"Did not find profile with uuid {str(used_profile_uuid)} in DB."
                )
        self._profile_uuids = list(uuids_used_in_setup)

    @db_session
    def buffer_profile_types(self):
        """
        Buffers profile types for the profiles of this simulation.
        """
        db_profile_uuids = self._get_profile_uuids_from_db()
        for profile_uuid in db_profile_uuids:
            datapoint = self.Profile_Database_ProfileInformation.get(profile_uuid=profile_uuid)
            self._profile_types[profile_uuid] = InputProfileTypes(datapoint.profile_type)

    @db_session
    def _buffer_all_profiles(self, current_timestamp: DateTime):
        """Loops over all profile uuids used in the setup and
        reads a new chunk of data from the DB

        Args:
            current_timestamp (Datetime): Current pendulum time stamp
        """
        start_time, end_time = self._get_start_end_time(current_timestamp)
        query_ret_val = self._get_profiles_from_db(
            self._convert_pendulum_to_datetime(start_time),
            self._convert_pendulum_to_datetime(end_time),
        )

        for profile_uuid in self._profile_uuids:
            self._user_profiles[profile_uuid] = {
                self._strip_timezone_and_create_pendulum_instance_from_datetime(
                    data_point.time
                ): data_point.value
                for data_point in query_ret_val
                if data_point.profile_uuid == profile_uuid
            }

        if GlobalConfig.is_canary_network():
            # do not try to get the first available data for canary networks
            return
        for profile_uuid, profile_timeseries in self._user_profiles.items():
            if not profile_timeseries:
                self._user_profiles[profile_uuid] = self.get_first_data_from_profile(
                    profile_uuid, current_timestamp
                )

    def _buffer_time_slots(self):
        """Buffers a list of time_slots that are currently buffered in the user profiles.
        These are user to decide whether to rotate the buffer

        """
        if len(self._profile_uuids) > 0:
            time_stamps = self._user_profiles[self._profile_uuids[0]].keys()
            self._buffered_times = list(time_stamps)
        else:
            self._buffered_times = []

    def _get_start_end_time(self, current_timestamp: DateTime) -> (DateTime, DateTime):
        """Gets the start and end time for the to be buffered profile.
        It uses generate_market_slot_list that takes into account the PROFILE_EXPANSION_DAYS

        Returns: tuple of timestamps

        """
        if GlobalConfig.is_canary_network():
            time_stamps = [
                self._convert_pendulum_to_datetime(current_timestamp),
                self._convert_pendulum_to_datetime(current_timestamp + self._buffer_duration),
            ]
        else:
            time_stamps = generate_market_slot_list(current_timestamp)
        if not time_stamps:
            log.error(
                "Empty market slot list. Current timestamp %s, duration %s, is canary %s, "
                "slot length %s",
                current_timestamp,
                GlobalConfig.sim_duration,
                GlobalConfig.is_canary_network(),
                GlobalConfig.slot_length,
            )
        return min(time_stamps), max(time_stamps)

    def _should_buffer_profiles(self, current_timestamp: DateTime):
        if GlobalConfig.is_canary_network():
            return True
        return self._profile_uuids is None or (
            not self._buffered_times or (current_timestamp not in self._buffered_times)
        )

    def buffer_profiles_from_db(self, current_timestamp: DateTime, uuids_used_in_setup: List):
        """Public method for buffering profiles and all other information from DB into memory

        Args:
            current_timestamp (Datetime): Current pendulum time stamp
                                          that is used to decide whether to buffer or not
            uuids_used_in_setup (List): list of profile uuids that are used in the simulation

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
        """Wrapper for acquiring a user profile for a specific profile_uuid

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
        self._scm_data_profiles = {}

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
    def current_timestamp(self) -> DateTime:
        """Get the current timestamp of the simulation"""
        return self._current_timestamp

    def _update_current_time(self, timestamp: DateTime):
        self._current_timestamp = timestamp

    @property
    def current_scm_profiles(self) -> Dict[str, SCMFeesRatesProfileDatapoint]:
        """
        Get SCM profiles for all areas for current timestamp. Return empty dict for simulations
        and non-SCM Canary Networks.
        """
        return self._scm_data_profiles

    def update_time_and_buffer_profiles(self, timestamp: DateTime, area: "Area") -> None:
        """Update current timestamp and get the first chunk of data from the DB"""
        self._update_current_time(timestamp)
        if self.db:
            uuids_used_in_setup = self._get_profile_uuids_from_setup(area)
            self.db.buffer_profiles_from_db(timestamp, uuids_used_in_setup)
            # To avoid circular import, this lazy import is required.
            # Proper fix would include moving this method to gsy_e_core/util.py.
            # pylint: disable=import-outside-toplevel
            from gsy_e.models.strategy.utils import is_scm_simulation

            if is_scm_simulation() and GlobalConfig.is_canary_network():
                self._scm_data_profiles = self.db.get_scm_data_profiles(
                    timestamp, gsy_e.constants.CONFIGURATION_ID
                )

    def read_new_datapoints_from_buffer_or_rotate_profile(
        self, profile, profile_uuid, profile_type
    ):
        """
        Read new datapoints from the profile buffer, and if the profile is not available rotate
        the profile by reading from the DB.
        """
        if should_read_profile_from_db(profile_uuid):
            db_profile = self.db.get_profile_from_db_buffer(profile_uuid)
            if not db_profile:
                db_profile = self.db.get_first_data_from_profile(
                    profile_uuid, self.current_timestamp
                )
            return read_arbitrary_profile(
                profile_type, db_profile, current_timestamp=self.current_timestamp
            )
        return read_arbitrary_profile(
            profile_type, profile, current_timestamp=self.current_timestamp
        )

    def rotate_profile(
        self,
        profile_type: InputProfileTypes,
        profile,
        profile_uuid: str = None,
        input_profile_path: str = None,
    ) -> Dict[DateTime, float]:
        """Reads a new chunk of profile if the buffer does not contain the current time stamp
        Profile chunks are either generated from single values, input daily profiles or profiles
        that are read from the DB

        Args:
            profile_type (InputProfileTypes): Type of the profile
            profile (any of str, dict, float): Any arbitrary input
                                               (same input as for read_arbitrary_profile)
            profile_uuid (str): optional, if set the profiles is read from the DB
            input_profile_path (str), optional, for profiles provided by files

        Returns: Profile chunk as dictionary

        """
        if profile_uuid is None and self.should_create_profile(profile):
            if input_profile_path:
                profile = input_profile_path
            return read_arbitrary_profile(
                profile_type, profile, current_timestamp=self.current_timestamp
            )
        if self.time_to_rotate_profile(profile):
            return self.read_new_datapoints_from_buffer_or_rotate_profile(
                profile, profile_uuid, profile_type
            )

        return profile

    def time_to_rotate_profile(self, profile):
        """Checks if current time_stamp is part of the populated profile"""
        return profile is None or self.current_timestamp not in profile.keys()

    def should_create_profile(self, profile):
        """Checks if profile is already a populated Dict[Datetime, float] dict
        or if it is an input value (str, int, dict)
        """
        return profile is not None and (
            not isinstance(profile, dict) or self.current_timestamp not in profile.keys()
        )

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
