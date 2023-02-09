"""
Copyright 2022 BC4P
This file is part of BC4P.

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
from gsy_e.models.area import Area
from gsy_e.models.strategy.infinite_bus import InfiniteBusStrategy
from gsy_framework.constants_limits import ConstSettings
from gsy_framework.database_connection.connection import InfluxConnection
from gsy_framework.database_connection.queries_fhac import QueryFHACAggregated
from gsy_e.models.strategy.external_strategies.pv import PVExternalStrategy
from gsy_e.models.strategy.external_strategies.storage import StorageExternalStrategy
from gsy_e.models.strategy.external_strategies.database import DatabaseLoadExternalStrategy

def get_setup(config):
    ConstSettings.GeneralSettings.RUN_IN_REALTIME = True
    connection_fhaachen = InfluxConnection("influx_fhaachen.cfg")

    ConstSettings.GeneralSettings.DEFAULT_UPDATE_INTERVAL = 1
    ConstSettings.MASettings.MARKET_TYPE = 2
    ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE = 22

    area = Area(
        "Grid",
        [
            Area(
                "FH Campus",
                [
                    Area("FH Load", strategy=DatabaseLoadExternalStrategy(query = QueryFHACAggregated(connection_fhaachen, power_column="P_ges", tablename="Strom"), initial_buying_rate=20, final_buying_rate=40)),
                    Area("FH PV", strategy=PVExternalStrategy(panel_count = 1, capacity_kW = 1200, initial_selling_rate=30, final_selling_rate=10)),
                    Area("FH Storage", strategy=StorageExternalStrategy(battery_capacity_kWh=1000, max_abs_battery_power_kW=150, initial_soc=50, initial_buying_rate=15, final_buying_rate=15, initial_selling_rate=35, final_selling_rate=35)),
                ], grid_fee_constant=0, external_connection_available=True),
            
            Area("Market Maker", strategy=InfiniteBusStrategy(energy_buy_rate=10, energy_sell_rate=40)),
        ],
        config=config, 
        grid_fee_constant=0, 
        external_connection_available=True
    )
    return area


# pip install -e .
# gsy-e run --setup bc4p.assets.fhcampus_storage --enable-external-connection --start-date 2022-11-09 --paused