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
from d3a.d3a_core.user_profile_handler import ProfileDBConnectionHandler
from d3a_interface.constants_limits import TIME_ZONE
from pendulum import today
from pony.orm import commit, db_session


class TestProfileDBConnectionHandler(ProfileDBConnectionHandler):

    @db_session
    def write_profile(self, config_uuid: str, area_uuid: str, profile_uuid: str, profile_type: int,
                      profile: dict):

        self.ConfigurationAreaProfileUuids(configuration_uuid=config_uuid,
                                           area_uuid=area_uuid,
                                           profile_uuid=profile_uuid,
                                           profile_type=profile_type)

        for time, value in profile.items():
            self.ProfileTimeSeries(profile_uuid=profile_uuid, time=time, value=value)
        commit()

    def disconnect(self):
        self._db.disconnect()
        self._db.provider = None
        self._db.schema = None


def copy_profile_to_multiple_days(daily_profile: dict, number_of_days: int):
    yearly_profile = {}
    for day in range(number_of_days):
        for time_stamp, value in daily_profile.items():
            yearly_profile[today(tz=TIME_ZONE).add(days=day,
                                                   hours=time_stamp.hour,
                                                   minutes=time_stamp.minute)] = value
    return yearly_profile


def write_yearly_user_profiles_to_db(daily_profile: dict,
                                     profile_type: int,
                                     config_uuid: str,
                                     area_uuid: str,
                                     profile_uuid: str):
    from integration_tests.environment import profiles_handler
    # TODO: increase to 1 year once needed
    yearly_profile = copy_profile_to_multiple_days(daily_profile, 5)

    profiles_handler.write_profile(config_uuid, area_uuid, profile_uuid,
                                   profile_type, yearly_profile)

    return config_uuid, area_uuid, profile_uuid
