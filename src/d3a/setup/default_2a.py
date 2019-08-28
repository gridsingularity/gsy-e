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
# from d3a.models.strategy.finite_power_plant import FinitePowerPlant
from d3a.models.strategy.storage import StorageStrategy
# from d3a.models.strategy.load_hours import CellTowerLoadHoursStrategy, LoadHoursStrategy
from d3a.models.appliance.pv import PVAppliance
from d3a.models.strategy.predefined_pv import PVPredefinedStrategy
# from d3a.models.strategy.pv import PVStrategy


def get_setup(config):
    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    # Area('H1 General Load', strategy=LoadHoursStrategy(avg_power_W=200,
                    #                                                    hrs_per_day=6,
                    #                                                    hrs_of_day=list(
                    #                                                        range(12, 18)),
                    #                                                    final_buying_rate=35),
                    #      appliance=SwitchableAppliance()),
                    # Area('H1 Storage1', strategy=StorageStrategy(initial_capacity_kWh=0.6),
                    #      appliance=SwitchableAppliance()),
                    Area('H1 Storage2', strategy=StorageStrategy(),
                         appliance=SwitchableAppliance()),
                ],
                transfer_fee_pct=0, transfer_fee_const=0,
            ),
            Area(
                'House 2',
                [
                    # Area('H2 General Load', strategy=LoadHoursStrategy(avg_power_W=200,
                    #                                                    hrs_per_day=4,
                    #                                                    hrs_of_day=list(
                    #                                                        range(12, 16)),
                    #                                                    final_buying_rate=35),
                    #      appliance=SwitchableAppliance()),
                    Area('H2 PV',
                         strategy=PVPredefinedStrategy(panel_count=4,
                                                       initial_selling_rate=30,
                                                       final_selling_rate=5,
                                                       cloud_coverage=0),
                         appliance=PVAppliance()),

                ],
                transfer_fee_pct=0, transfer_fee_const=0,

            ),
            # Area('Cell Tower', strategy=CellTowerLoadHoursStrategy(avg_power_W=100,
            #                                                        hrs_per_day=24,
            #                                                        hrs_of_day=list(range(0, 24)),
            #                                                        final_buying_rate=2),
            #      appliance=SwitchableAppliance()),
            # Area('Commercial Energy Producer',
            #      strategy=CommercialStrategy(energy_rate=30),
            #      appliance=SimpleAppliance()
            #      ),

        ],
        config=config
    )
    return area
