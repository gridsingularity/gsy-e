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

from pendulum import DateTime, timezone
from gsy_framework.enums import GridIntegrationType

from gsy_e.models.area import Area
from gsy_e.models.strategy.commercial_producer import CommercialStrategy
from gsy_e.models.strategy.ev_charger import EVChargerStrategy, EVChargingSession
from gsy_e.models.strategy.load_hours import LoadHoursStrategy


def get_setup(config):
    area = Area(
        "Grid",
        children=[
            Area(
                "House 1",
                children=[
                    Area(
                        "H1 General Load",
                        strategy=LoadHoursStrategy(
                            avg_power_W=200, hrs_of_day=list(range(0, 24)), final_buying_rate=27
                        ),
                    ),
                    Area(
                        "H1 EV Charger",
                        strategy=EVChargerStrategy(
                            grid_integration=GridIntegrationType.BIDIRECTIONAL,
                            maximum_power_rating_kW=10,  # same as storage_buys_and_offers
                            charging_sessions=[
                                EVChargingSession(
                                    plug_in_time=DateTime.now(tz=timezone("UTC")).start_of("day"),
                                    duration_minutes=60,
                                    initial_soc_percent=50,  # same as storage_buys_and_offers
                                    battery_capacity_kWh=30,  # same as storage_buys_and_offers
                                )
                            ],
                        ),
                    ),
                ],
            ),
            Area("Commercial Energy Producer", strategy=CommercialStrategy(energy_rate=22)),
        ],
        config=config,
    )
    return area
