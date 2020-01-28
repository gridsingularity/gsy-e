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
from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.area import Area
from d3a.models.strategy.finite_power_plant import FinitePowerPlant
from d3a.models.strategy.load_hours import LoadHoursStrategy
from d3a_interface.constants_limits import ConstSettings


def get_setup(config):
    ConstSettings.IAASettings.MARKET_TYPE = 3

    area = Area(
        'Grid',
        [
            Area(
                'Energy Community',
                [
                    Area('Load 1', strategy=LoadHoursStrategy(
                        avg_power_W=500, hrs_per_day=24, hrs_of_day=list(range(24)),
                        initial_buying_rate=10, final_buying_rate=10),
                         appliance=SwitchableAppliance()),
                    Area('Load 2', strategy=LoadHoursStrategy(
                        avg_power_W=500, hrs_per_day=24, hrs_of_day=list(range(24)),
                        initial_buying_rate=15, final_buying_rate=15),
                         appliance=SwitchableAppliance()),
                    Area('Load 3', strategy=LoadHoursStrategy(
                        avg_power_W=500, hrs_per_day=24, hrs_of_day=list(range(24)),
                        initial_buying_rate=30, final_buying_rate=30),
                         appliance=SwitchableAppliance()),
                    Area('Local Supply',
                         strategy=FinitePowerPlant(energy_rate=10, max_available_power_kW=1.0),
                         appliance=SimpleAppliance()),
                ],
                transfer_fee_pct=5,
            ),
        ],
        config=config
    )
    return area
