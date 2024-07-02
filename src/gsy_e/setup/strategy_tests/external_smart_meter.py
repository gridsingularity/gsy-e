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
from pathlib import Path

from gsy_framework.constants_limits import ConstSettings

from gsy_e.gsy_e_core.util import gsye_root_path
from gsy_e.models.area import Area
from gsy_e.models.strategy.commercial_producer import CommercialStrategy
from gsy_e.models.strategy.external_strategies.smart_meter import SmartMeterExternalStrategy
from gsy_e.models.strategy.load_hours import LoadHoursStrategy
from gsy_e.models.strategy.storage import StorageStrategy

ConstSettings.MASettings.MARKET_TYPE = 2


def get_setup(config):
    """Return the setup to be used for the simulation."""
    area = Area(
        "Grid",
        [
            Area(
                "House 1",
                [
                    Area("load", strategy=LoadHoursStrategy(
                        hrs_of_day=list(range(2, 24)), avg_power_W=4000,
                        initial_buying_rate=0, final_buying_rate=30),
                    ),
                    Area("storage", strategy=StorageStrategy(initial_soc=50)),
                    Area("smart_meter", strategy=SmartMeterExternalStrategy(
                        smart_meter_profile=(
                                Path(gsye_root_path) / "resources/smart_meter_profile.csv"))),
                    Area("commercial_producer", strategy=CommercialStrategy(energy_rate=30)),
                ],
            ),
        ],
        config=config
    )
    return area
