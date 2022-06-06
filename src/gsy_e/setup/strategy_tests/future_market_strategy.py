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
    ConstSettings.SettlementMarketSettings.ENABLE_SETTLEMENT_MARKETS = (
        False  # De-activate Settlement Market
    )
    GlobalConfig.FUTURE_MARKET_DURATION_HOURS = (
        2  # This flag controls the number of open future markets (4 in this case)
    )
    ConstSettings.FutureMarketSettings.FUTURE_MARKET_CLEARING_INTERVAL_MINUTES = (
        15
        # The frequency at which Futures market is cleared -
        # doesn't impact the calculation of the rate
    )
    ConstSettings.MASettings.MARKET_TYPE = 2

    # FutureTemplateStrategiesConstants.INITIAL_BUYING_RATE = 0
    FutureTemplateStrategiesConstants.FINAL_BUYING_RATE = 30  # 60
    # for FINAL_BUYING_RATE = 30, seems like the buying rate is not the
    # top most value in the results, but 50 cts/kWh is the highest bidding/selling energy rate.
    FutureTemplateStrategiesConstants.UPDATE_INTERVAL_MIN = 15
    FutureTemplateStrategiesConstants.INITIAL_SELLING_RATE = 30
    # FutureTemplateStrategiesConstants.FINAL_SELLING_RATE = 0

    area = Area(
        "Grid",
        [
            Area(
                "Community",
                [
                    Area(
                        "House 1",
                        [
                            Area(
                                "H1 Load",
                                strategy=LoadHoursStrategy(
                                    avg_power_W=200,
                                    hrs_per_day=6,
                                    hrs_of_day=list(range(12, 18)),
                                    final_buying_rate=35,
                                ),
                            ),
                            Area("H1 PV", strategy=PVStrategy(panel_count=4)),
                        ],
                    ),
                    Area(
                        "House 2",
                        [
                            Area(
                                "H2 Load",
                                strategy=LoadHoursStrategy(
                                    avg_power_W=200,
                                    hrs_per_day=24,
                                    hrs_of_day=list(range(0, 24)),
                                    final_buying_rate=35,
                                ),
                            ),
                            Area(
                                "H2 ESS",
                                strategy=StorageStrategy(
                                    initial_soc=100, battery_capacity_kWh=20
                                ),
                            ),
                            Area("H2 PV", strategy=PVStrategy(panel_count=4)),
                        ],
                    ),
                ],
            ),
            Area(
                "Market Maker",
                strategy=InfiniteBusStrategy(energy_buy_rate=21, energy_sell_rate=22),
            ),
        ],
        config=config,
    )
    return area
