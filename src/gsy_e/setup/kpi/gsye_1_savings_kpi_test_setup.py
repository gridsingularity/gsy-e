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

from gsy_e.models.area import Area
from gsy_e.models.strategy.infinite_bus import InfiniteBusStrategy
from gsy_e.models.strategy.load_hours import LoadHoursStrategy
from gsy_e.models.strategy.pv import PVStrategy
from gsy_e.models.strategy.storage import StorageStrategy


def get_setup(config):
    """
    This setup is used in an integration test that checks if the savings_kpi endpoint calculates
    the expected values. It was added after it was decided to also export savings for the community
    layer. The setup contains all kinds of assets (producers, consumers, prosumers) in both the
    home and community layer in order to check the handling of all.
    """

    ConstSettings.MASettings.MARKET_TYPE = 2
    ConstSettings.MASettings.MIN_OFFER_AGE = 0
    ConstSettings.MASettings.MIN_BID_AGE = 0

    area = Area(
        "Grid",
        [
            Area(
                "Community",
                [
                    Area("Home",
                         [
                             Area("Home Load", strategy=LoadHoursStrategy(
                                 avg_power_W=3147, hrs_of_day=list(range(24)),
                                 initial_buying_rate=25, final_buying_rate=25,
                                 fit_to_limit=True)),
                             Area("Home PV", strategy=PVStrategy(
                                 capacity_kW=4, panel_count=1,
                                 initial_selling_rate=30, final_selling_rate=2)),
                             Area("Home ESS", strategy=StorageStrategy(
                                 initial_soc=20, battery_capacity_kWh=5,
                                 initial_buying_rate=22.94, final_buying_rate=22.94,
                                 initial_selling_rate=22.95, final_selling_rate=22.95))
                         ]),
                    Area("Community PV", strategy=PVStrategy(
                        capacity_kW=4, panel_count=1,
                        initial_selling_rate=30, final_selling_rate=2)),
                    Area("Community Load", strategy=LoadHoursStrategy(
                        avg_power_W=400, hrs_of_day=list(range(24)),
                        initial_buying_rate=25.5, final_buying_rate=25.5,
                        fit_to_limit=True)),
                    Area("Community ESS", strategy=StorageStrategy(
                        initial_soc=20, battery_capacity_kWh=5,
                        initial_buying_rate=22.94, final_buying_rate=22.94,
                        initial_selling_rate=22.95, final_selling_rate=22.95))

                ], grid_fee_constant=4.0),
            Area("MarketMaker",
                 strategy=InfiniteBusStrategy(energy_buy_rate=16, energy_sell_rate=22))
        ],
        config=config, grid_fee_constant=4.0,
    )
    return area
