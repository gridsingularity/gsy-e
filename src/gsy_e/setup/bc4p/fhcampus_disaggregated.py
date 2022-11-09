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
from gsy_e.models.strategy.influx import InfluxLoadStrategy
from gsy_e.models.strategy.pv import PVStrategy
from gsy_framework.influx_connection.connection import InfluxConnection
from gsy_framework.influx_connection.queries_fhac import DataFHAachenAggregated
from gsy_e.models.strategy.storage import StorageStrategy

def get_setup(config):
    ConstSettings.GeneralSettings.RUN_IN_REALTIME = True
    connection_fhaachen = InfluxConnection("influx_fhaachen.cfg")

    area = Area(
        "Grid",
        [
            Area("FH Campus Load", strategy=InfluxLoadStrategy(query = DataFHAachenAggregated(connection_fhaachen, power_column="P_ges", tablename="Strom"), initial_buying_rate=20, final_buying_rate=40)),
            Area("FH Campus PV", strategy=PVStrategy(panel_count = 1, capacity_kW = 300, initial_selling_rate=30, final_selling_rate=10)),
            Area("Infinite Bus", strategy=InfiniteBusStrategy(energy_buy_rate=10, energy_sell_rate=40)),
            Area("Fh Campus Storage", strategy=StorageStrategy(battery_capacity_kWh=90, max_abs_battery_power_kW=30, initial_soc=50, initial_buying_rate=11, final_buying_rate=19, initial_selling_rate=39, final_selling_rate=31)),
        ],
        config=config
    )
    return area


# pip install -e .
# gsy-e run --setup bc4p_fhcampus -s 15m --enable-external-connection --start-date 2022-11-07