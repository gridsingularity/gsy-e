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
from gsy_framework.constants_limits import ConstSettings

from gsy_e.constants import FutureTemplateStrategiesConstants
from gsy_e.models.area import Area
from gsy_e.models.strategy.external_strategies.load import (
    LoadHoursStrategy,
)
from gsy_e.models.strategy.external_strategies.pv import PVStrategy
from gsy_e.models.strategy.external_strategies.storage import (
    StorageStrategy,
)

current_dir = os.path.dirname(__file__)


def get_setup(config):
    ConstSettings.MASettings.MARKET_TYPE = 2
    ConstSettings.FutureMarketSettings.FUTURE_MARKET_DURATION_HOURS = (
        get_var_from_env("FUTURE_MARKET_DURATION_HOURS", 1)
    )
    ConstSettings.FutureMarketSettings.FUTURE_MARKET_CLEARING_INTERVAL_MINUTES = (
        get_var_from_env("FUTURE_MARKET_CLEARING_INTERVAL_MINUTES", 5)
    )
    FutureTemplateStrategiesConstants.UPDATE_INTERVAL_MIN = get_var_from_env(
        "UPDATE_INTERVAL_MIN", 5
    )
    FutureTemplateStrategiesConstants.INITIAL_BUYING_RATE = get_var_from_env(
        "INITIAL_BUYING_RATE", 0
    )
    FutureTemplateStrategiesConstants.FINAL_BUYING_RATE = get_var_from_env(
        "FINAL_BUYING_RATE", 50
    )
    FutureTemplateStrategiesConstants.INITIAL_SELLING_RATE = get_var_from_env(
        "INITIAL_SELLING_RATE", 50
    )
    FutureTemplateStrategiesConstants.FINAL_SELLING_RATE = get_var_from_env(
        "FINAL_SELLING_RATE", 0
    )

    area = Area(
        "Grid-Community",
        [
            Area("House 1",
                 [
                     Area(
                         "Load",
                         strategy=LoadHoursStrategy(
                             avg_power_W=100000,
                             hrs_of_day=list(range(0, 24)),
                             initial_buying_rate=3,
                             final_buying_rate=24,
                         ),
                     ),
                     Area(
                         "PV", strategy=PVStrategy(
                             panel_count=1, initial_selling_rate=47, final_selling_rate=25)
                     ),
                     Area(
                         "ESS",
                         strategy=StorageStrategy(
                             initial_soc=50, battery_capacity_kWh=1000000,
                             initial_selling_rate=47, final_selling_rate=25,
                             initial_buying_rate=3, final_buying_rate=24)
                     )
                 ]
                 )
        ], config=config,
    )

    return area


def get_var_from_env(var_name: str, default_val: float):
    """Read variable from env and parse as string"""
    var = os.environ.get(var_name)
    if var is not None:
        return float(var)
    return default_val
