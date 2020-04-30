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
from d3a.models.area import Area
from d3a.models.strategy.finite_power_plant import FinitePowerPlant
from d3a.models.strategy.market_maker_strategy import MarketMakerStrategy
from d3a.models.strategy.load_hours import LoadHoursStrategy
from d3a_interface.constants_limits import ConstSettings


def get_setup(config):
    ConstSettings.IAASettings.MARKET_TYPE = 2
    area = Area(
        'Grid',
        [
            Area(
                'Community',
                [
                    Area('H1',
                         [
                            Area('Load', strategy=LoadHoursStrategy(avg_power_W=1000,
                                                                    hrs_per_day=1,
                                                                    hrs_of_day=list(
                                                                       range(10, 11)),
                                                                    initial_buying_rate=60,
                                                                    final_buying_rate=60,
                                                                    update_interval=1),
                                 appliance=SwitchableAppliance()),
                         ], transfer_fee_const=2)
                ],
                transfer_fee_const=3,
            ),
            Area(
                'DSO',
                [
                    Area('Power Plant', strategy=FinitePowerPlant(energy_rate=30,
                                                                  max_available_power_kW=1000),
                         appliance=SwitchableAppliance()),
                ],
                transfer_fee_const=10,
            ),
            Area('Market Maker', strategy=MarketMakerStrategy(grid_connected=True, energy_rate=50),
                 appliance=SwitchableAppliance()),
        ], transfer_fee_const=10,
        config=config
    )
    return area
