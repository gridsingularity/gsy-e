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
from gsy_framework.constants_limits import ConstSettings
from gsy_framework.enums import AvailableMarketTypes, SpotMarketTypeEnum
from pendulum import duration

from gsy_e.models.area import Area
from gsy_e.models.strategy.forward.load import ForwardLoadStrategy
from gsy_e.models.strategy.forward.order_updater import ForwardOrderUpdaterParameters
from gsy_e.models.strategy.forward.pv import ForwardPVStrategy

ConstSettings.ForwardMarketSettings.ENABLE_FORWARD_MARKETS = True
ConstSettings.ForwardMarketSettings.FULLY_AUTO_TRADING = True
ConstSettings.MASettings.MARKET_TYPE = SpotMarketTypeEnum.TWO_SIDED.value

load_updaters = {
    AvailableMarketTypes.INTRADAY: ForwardOrderUpdaterParameters(
        duration(minutes=5), 10, 40, 10),
    AvailableMarketTypes.DAY_FORWARD: ForwardOrderUpdaterParameters(
        duration(minutes=30), 20, 40, 10),
    AvailableMarketTypes.WEEK_FORWARD: ForwardOrderUpdaterParameters(
        duration(days=1), 30, 50, 10),
    AvailableMarketTypes.MONTH_FORWARD: ForwardOrderUpdaterParameters(
        duration(weeks=1), 40, 60, 20),
    AvailableMarketTypes.YEAR_FORWARD: ForwardOrderUpdaterParameters(
        duration(months=1), 50, 70, 50)
}


pv_updaters = {
    AvailableMarketTypes.INTRADAY: ForwardOrderUpdaterParameters(
        duration(minutes=5), 10, 10, 10),
    AvailableMarketTypes.DAY_FORWARD: ForwardOrderUpdaterParameters(
        duration(minutes=30), 10, 10, 10),
    AvailableMarketTypes.WEEK_FORWARD: ForwardOrderUpdaterParameters(
        duration(days=1), 10, 10, 10),
    AvailableMarketTypes.MONTH_FORWARD: ForwardOrderUpdaterParameters(
        duration(weeks=1), 10, 10, 20),
    AvailableMarketTypes.YEAR_FORWARD: ForwardOrderUpdaterParameters(
        duration(months=1), 10, 10, 50)
}


def get_setup(config):
    area = Area(
        "Grid",
        [
            Area(
                "General Load",
                strategy=ForwardLoadStrategy(
                    capacity_kW=1000,
                    order_updater_parameters=load_updaters
                ),
            ),
            Area(
                "PV",
                strategy=ForwardPVStrategy(
                    capacity_kW=50000,
                    order_updater_parameters=pv_updaters
                ),
            ),
        ],
        config=config,
    )
    return area
