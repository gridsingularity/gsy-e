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
from gsy_framework.constants_limits import (ConstSettings, GlobalConfig)

from gsy_e.constants import FutureTemplateStrategiesConstants
from gsy_e.models.area import Area
from gsy_e.models.strategy.external_strategies.load import (
    LoadHoursStrategy,
)
from gsy_e.models.strategy.external_strategies.pv import PVStrategy
from gsy_e.models.strategy.external_strategies.storage import (
    StorageStrategy,
)
from gsy_e.models.strategy.infinite_bus import InfiniteBusStrategy

current_dir = os.path.dirname(__file__)


def get_setup(config):
    GlobalConfig.FUTURE_MARKET_DURATION_HOURS = (
        os.environ.get("FUTURE_MARKET_DURATION_HOURS", 1)
    )
    ConstSettings.FutureMarketSettings.FUTURE_MARKET_CLEARING_INTERVAL_MINUTES = (
        os.environ.get("FUTURE_MARKET_CLEARING_INTERVAL_MINUTES", 15)
    )
    ConstSettings.MASettings.MARKET_TYPE = 2

    FutureTemplateStrategiesConstants.INITIAL_BUYING_RATE = os.environ.get(
        "INITIAL_BUYING_RATE", 0
    )
    FutureTemplateStrategiesConstants.FINAL_BUYING_RATE = os.environ.get(
        "FINAL_BUYING_RATE", 50
    )
    FutureTemplateStrategiesConstants.INITIAL_SELLING_RATE = os.environ.get(
        "INITIAL_SELLING_RATE", 50
    )
    FutureTemplateStrategiesConstants.FINAL_SELLING_RATE = os.environ.get(
        "FINAL_SELLING_RATE", 0
    )

    FutureTemplateStrategiesConstants.UPDATE_INTERVAL_MIN = os.environ.get(
        "UPDATE_INTERVAL_MIN", 5
    )

    area = Area(
        "Grid-Community",
        [
            Area(
                "Load",
                strategy=LoadHoursStrategy(
                    avg_power_W=1000,
                    hrs_per_day=24,
                    hrs_of_day=list(range(0, 24)),
                    initial_buying_rate=15,
                    final_buying_rate=25,
                ),
            ),
            Area(
                "PV", strategy=PVStrategy(
                    panel_count=4, initial_selling_rate=30, final_selling_rate=15)
            ),
            Area(
                "Market Maker",
                strategy=InfiniteBusStrategy(
                    energy_buy_rate=28, energy_sell_rate=30),
            ),
            Area(
                "ESS",
                strategy=StorageStrategy(
                    initial_soc=100, battery_capacity_kWh=20,
                    initial_selling_rate=30, final_selling_rate=20,
                    initial_buying_rate=15, final_buying_rate=20)
            )

        ],
        config=config,
    )
    return area
