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
from d3a_interface.constants_limits import ConstSettings
from d3a.models.strategy.infinite_bus import InfiniteBusStrategy
from d3a.models.strategy.load_hours import LoadHoursStrategy


def get_setup(config):

    ConstSettings.GeneralSettings.DEFAULT_UPDATE_INTERVAL = 1
    ConstSettings.IAASettings.MARKET_TYPE = 2

    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    Area('H1 General Load', strategy=LoadHoursStrategy(avg_power_W=4000,
                                                                       hrs_per_day=1,
                                                                       hrs_of_day=list(
                                                                           range(1, 2)),
                                                                       initial_buying_rate=45,
                                                                       final_buying_rate=45,
                                                                       fit_to_limit=True),
                         appliance=SwitchableAppliance()),
                ], transfer_fee_pct=0, transfer_fee_const=0,
            ),
            Area('DSO', strategy=InfiniteBusStrategy(energy_buy_rate=5, energy_sell_rate=30),
                 appliance=SimpleAppliance()),
        ],
        config=config, transfer_fee_pct=50, transfer_fee_const=0,
    )
    return area
