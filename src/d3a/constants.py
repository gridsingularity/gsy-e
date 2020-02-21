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
# Need to import required settings from d3a-interface in order to be available in d3a,
# thus avoiding accessing the d3a-interface constants.
from d3a_interface.constants_limits import TIME_FORMAT, DATE_FORMAT # NOQA
from d3a_interface.constants_limits import DATE_TIME_FORMAT, DATE_TIME_UI_FORMAT  # NOQA

# *IMPORTANT*: Don't manually change the version here. Use the 'bumpversion' utility.
VERSION = "1.0.0a0"

TIME_ZONE = "UTC"

DEFAULT_PRECISION = 8
FLOATING_POINT_TOLERANCE = 0.00001

REDIS_PUBLISH_RESPONSE_TIMEOUT = 1
MAX_WORKER_THREADS = 10

DISPATCH_EVENTS_BOTTOM_TO_TOP = True
# Controls how often will event tick be dispatched to external connections. Defaults to
# 20% of the slot length
DISPATCH_EVENT_TICK_FREQUENCY_PERCENT = 20

COLLABORATION_ID = ""
# Controls whether the external connection is for use with the redis api client
# or with the d3a-web. Default is to connect via Redis.
EXTERNAL_CONNECTION_WEB = False
