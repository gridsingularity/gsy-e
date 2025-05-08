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

# Need to import required settings from gsy-framework in order to be available in d3a,
# thus avoiding accessing the gsy-framework constants.
# pylint: disable=unused-import
import os

EXPORT_STATS_ROUND_TOLERANCE = 3

# Percentual standard deviation relative to the forecast energy, used to compute the (simulated)
# real energy produced/consumed by a device.
RELATIVE_STD_FROM_FORECAST_ENERGY = 10

REDIS_PUBLISH_RESPONSE_TIMEOUT = 1
MAX_WORKER_THREADS = 10

DISPATCH_EVENTS_BOTTOM_TO_TOP = True
# Controls how often will event tick be dispatched to external connections. Defaults to
# 20% of the slot length
DISPATCH_EVENT_TICK_FREQUENCY_PERCENT = 10
DISPATCH_MATCHING_ENGINE_EVENT_TICK_FREQUENCY_PERCENT = 2

CONFIGURATION_ID = os.environ.get("CONFIGURATION_ID", "")
# Controls whether the external connection is for use with the redis api client
# or with the gsy-web. Default is to connect via Redis.
EXTERNAL_CONNECTION_WEB = False

SIMULATION_PAUSE_TIMEOUT = 600

# Controls whether the past markets and the strategy state (bids / offers that are buffered in the
# strategy classes) are still being kept in the simulation memory for the duration
# of the simulation. Helpful in the unit / integration tests, since some of these rely on the
# markets remaining in-memory until the end of the simulation run.
# Is also needed for the raw JSON files and the plots when running in CLI mode.
# Also helpful when debugging, in order for the interpreter to have access to all markets that a
# simulation has ran through.
RETAIN_PAST_MARKET_STRATEGIES_STATE = False
KAFKA_MOCK = False

CN_PROFILE_EXPANSION_DAYS = 7

RUN_IN_REALTIME = False

CONNECT_TO_PROFILES_DB = False
SEND_EVENTS_RESPONSES_TO_SDK_VIA_RQ = False

RUN_IN_NON_P2P_MODE = False

DEFAULT_SCM_COMMUNITY_NAME = "Community"
DEFAULT_SCM_GRID_NAME = "Grid"
SCM_DISABLE_HOME_SELF_CONSUMPTION = False


FORWARD_MARKET_MAX_DURATION_YEARS = 6

MIN_OFFER_BID_AGE_P2P_DISABLED = 360


class SettlementTemplateStrategiesConstants:
    """Constants related to the configuration of settlement template strategies"""

    INITIAL_BUYING_RATE = 0
    FINAL_BUYING_RATE = 50
    INITIAL_SELLING_RATE = 50
    FINAL_SELLING_RATE = 0

    UPDATE_INTERVAL_MIN = 5


class FutureTemplateStrategiesConstants(SettlementTemplateStrategiesConstants):
    """Constants related to the configuration of future template strategies"""
