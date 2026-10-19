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

import csv
import os

from gsy_framework.constants_limits import ConstSettings

from gsy_e.gsy_e_core.util import gsye_root_path
from gsy_e.models.area import Area
from gsy_e.models.strategy.infinite_bus import InfiniteBusStrategy
from gsy_e.models.strategy.predefined_load import DefinedLoadStrategy
from gsy_e.models.strategy.predefined_pv import PVUserProfileStrategy

SUPPLIER_RATE = 26
PEAK_FACTOR = 1.35
PEAK_HOURS = range(17, 21)
GRID_FEE = 4
COMMUNITY_SALE_RATE = 14
FEED_IN_RATE = 8
COMMUNITY_SHARE_OF_SURPLUS = 0.3


def _read_hourly_kWh(file_name):
    with open(os.path.join(gsye_root_path, "resources", file_name), encoding="utf-8") as file:
        return [float(kWh) for _, kWh in csv.reader(file)]


def _hourly_profile(start_date, values):
    return {start_date.add(hours=hour): value for hour, value in enumerate(values)}


def get_setup(config):
    """Mirror the single-owner week of PV_RoI_Reference_Model.xlsx on hourly slots."""
    ConstSettings.MASettings.MARKET_TYPE = 2
    start = config.start_date
    pv_generation = _read_hourly_kWh("PV_RoI_reference_generation_kWh.csv")
    load = _read_hourly_kWh("PV_RoI_reference_load_kWh.csv")
    supplier_rates = [
        SUPPLIER_RATE * (PEAK_FACTOR if hour % 24 in PEAK_HOURS else 1)
        for hour in range(len(pv_generation))
    ]
    community_purchases = [
        COMMUNITY_SHARE_OF_SURPLUS * max(generation - consumption, 0)
        for generation, consumption in zip(pv_generation, load)
    ]
    return Area(
        "Grid",
        [
            Area(
                "Supplier",
                strategy=InfiniteBusStrategy(
                    energy_rate_profile=_hourly_profile(start, supplier_rates),
                    energy_buy_rate=FEED_IN_RATE + GRID_FEE,
                ),
            ),
            Area(
                "Community",
                [
                    Area(
                        "House",
                        [
                            Area(
                                "PV",
                                strategy=PVUserProfileStrategy(
                                    power_profile=_hourly_profile(start, pv_generation),
                                    initial_selling_rate=COMMUNITY_SALE_RATE - 1,
                                    final_selling_rate=FEED_IN_RATE,
                                    capacity_kW=5,
                                    capital_cost_per_kwp=1300,
                                    annual_generation_kWh=4900,
                                ),
                            ),
                            Area(
                                "Load",
                                strategy=DefinedLoadStrategy(
                                    daily_load_profile=_hourly_profile(start, load),
                                    initial_buying_rate=40,
                                    final_buying_rate=40,
                                ),
                            ),
                        ],
                        grid_fee_constant=0,
                    ),
                    Area(
                        "Neighbour",
                        strategy=DefinedLoadStrategy(
                            daily_load_profile=_hourly_profile(start, community_purchases),
                            initial_buying_rate=COMMUNITY_SALE_RATE,
                            final_buying_rate=COMMUNITY_SALE_RATE,
                        ),
                    ),
                ],
                grid_fee_constant=0,
            ),
        ],
        grid_fee_constant=GRID_FEE,
        config=config,
    )
