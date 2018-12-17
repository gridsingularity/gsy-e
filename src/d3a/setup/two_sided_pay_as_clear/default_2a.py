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
# from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
# from d3a.models.strategy.commercial_producer import CommercialStrategy
from d3a.models.strategy.load_hours import LoadHoursStrategy, CellTowerLoadHoursStrategy
from d3a.models.appliance.pv import PVAppliance
from d3a.models.strategy.pv import PVStrategy
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.const import ConstSettings


def get_setup(config):

    ConstSettings.IAASettings.MARKET_TYPE = 3
    ConstSettings.GeneralSettings.MARKET_CLEARING_FREQUENCY_PER_SLOT = 3
    ConstSettings.LoadSettings.MIN_ENERGY_RATE = 35
    ConstSettings.LoadSettings.MAX_ENERGY_RATE = 35
    ConstSettings.StorageSettings.MIN_BUYING_RATE = 24.99
    ConstSettings.StorageSettings.BREAK_EVEN_BUY = 25
    ConstSettings.StorageSettings.BREAK_EVEN_SELL = 25.01

    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    Area('H1 General Load', strategy=LoadHoursStrategy(avg_power_W=100,
                                                                       hrs_per_day=6,
                                                                       hrs_of_day=list(
                                                                           range(12, 18)),
                                                                       max_energy_rate=35),
                         appliance=SwitchableAppliance()),
                    Area('H1 Storage1', strategy=StorageStrategy(
                        initial_capacity_kWh=0.6,
                        break_even=(ConstSettings.StorageSettings.BREAK_EVEN_BUY,
                                    ConstSettings.StorageSettings.BREAK_EVEN_SELL)),
                         appliance=SwitchableAppliance()),
                    Area('H1 Storage2', strategy=StorageStrategy(
                        initial_capacity_kWh=0.6,
                        break_even=(ConstSettings.StorageSettings.BREAK_EVEN_BUY,
                                    ConstSettings.StorageSettings.BREAK_EVEN_SELL)),
                         appliance=SwitchableAppliance()),
                ]
            ),
            Area(
                'House 2',
                [
                    Area('H2 General Load', strategy=LoadHoursStrategy(
                        avg_power_W=100,
                        hrs_per_day=4,
                        hrs_of_day=list(
                            range(12, 16)),
                        min_energy_rate=ConstSettings.LoadSettings.MIN_ENERGY_RATE,
                        max_energy_rate=35),
                         appliance=SwitchableAppliance()),
                    Area('H2 PV', strategy=PVStrategy(4, 0),
                         appliance=PVAppliance()),

                ]
            ),
            Area('Cell Tower', strategy=CellTowerLoadHoursStrategy(
                avg_power_W=100,
                hrs_per_day=24,
                hrs_of_day=list(range(0, 24)),
                min_energy_rate=ConstSettings.LoadSettings.MIN_ENERGY_RATE,
                max_energy_rate=35),
                 appliance=SwitchableAppliance())
            # Area('Commercial Energy Producer',
            #      strategy=CommercialStrategy(energy_range_wh=(40, 120), energy_price=30),
            #      appliance=SimpleAppliance()
            #      ),

        ],
        config=config
    )
    return area
