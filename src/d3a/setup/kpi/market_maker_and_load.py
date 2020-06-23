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
from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
from d3a.models.strategy.market_maker_strategy import MarketMakerStrategy
from d3a.models.strategy.load_hours import LoadHoursStrategy
from d3a_interface.constants_limits import ConstSettings


def get_setup(config):
    # Left this for testing that the KPIs export also works with KEEP_PAST_MARKETS
    ConstSettings.GeneralSettings.KEEP_PAST_MARKETS = True
    area = Area(
        'Grid',
        [
            Area('H1 General Load', strategy=LoadHoursStrategy(avg_power_W=100,
                                                               hrs_per_day=9,
                                                               hrs_of_day=list(
                                                                   range(8, 18))),
                 appliance=SwitchableAppliance()),

            Area('Market Maker',
                 strategy=MarketMakerStrategy(energy_rate=30,
                                              grid_connected=True),
                 appliance=SimpleAppliance()
                 ),

        ],
        config=config
    )
    return area
