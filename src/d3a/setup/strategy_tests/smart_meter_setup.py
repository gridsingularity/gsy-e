"""
Copyright 2018 Grid Singularity
This file is part of D3A.

This program is free software: you can redistribute it and/or modify it under the terms of the
GNU General Public License as published by the Free Software Foundation, either version 3 of the
License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See
the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with this program. If
not, see <http://www.gnu.org/licenses/>.
"""
from pathlib import Path

from d3a.models.area import Area
from d3a.models.strategy.commercial_producer import CommercialStrategy
from d3a.models.strategy.smart_meter import SmartMeterStrategy
from d3a.models.strategy.load_hours import LoadHoursStrategy
from d3a.models.strategy.storage import StorageStrategy
from d3a.gsy_e_core.util import d3a_path


def get_setup(config):
    """Returns a setup that allows testing a Smart Meter device and its profile."""
    area = Area(
        "Grid",
        [
            Area("House 1", [
                Area("H1 Load", strategy=LoadHoursStrategy(
                     avg_power_W=200, hrs_per_day=6, hrs_of_day=list(range(12, 18)),
                     final_buying_rate=35)),
                Area("H1 Storage 1", strategy=StorageStrategy(initial_soc=50))
                ],
                grid_fee_percentage=0, grid_fee_constant=0,
            ),
            Area("House 2 Smart Meter", strategy=SmartMeterStrategy(
                initial_selling_rate=30, final_selling_rate=5,
                smart_meter_profile=Path(d3a_path) / "resources/smart_meter_profile.csv")),
            Area("Commercial Energy Producer", strategy=CommercialStrategy(energy_rate=30)),
        ],
        config=config
    )
    return area
