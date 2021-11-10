"""
Copyright 2018 Grid Singularity
This file is part of D3A.

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
from gsy_e.models.strategy.pv import PVStrategy
from gsy_e.models.strategy.external_strategies.storage import StorageExternalStrategy
from gsy_framework.constants_limits import ConstSettings

ConstSettings.IAASettings.MARKET_TYPE = 2


def get_setup(config):
    area = Area(
        "Grid",
        [
            Area(
                "House 1",
                [
                    # TODO: initial_selling_rate is adjusted from 30 to 40, in order to avoid
                    #  getting instantly matched with incoming bids from external ess agent.
                    #  To be re-checked in context to D3ASIM-3220(replace_existing)
                    Area("PV", strategy=PVStrategy(
                        capacity_kW=2, initial_selling_rate=40, final_selling_rate=30.0)
                         ),
                    Area("storage", strategy=StorageExternalStrategy(
                        initial_soc=50, battery_capacity_kWh=20)
                         ),
                ],
            ),
        ],
        config=config
    )
    return area
