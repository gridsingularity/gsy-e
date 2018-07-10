"""
Setup file for displaying the finite power plant strategy.
"""

from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.strategy.load_hours_fb import LoadHoursStrategy, CellTowerLoadHoursStrategy
from d3a.models.strategy.commercial_producer import CommercialStrategy
from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.appliance.pv import PVAppliance
from d3a.models.strategy.pv import PVStrategy

"""
Finite power plant strategy requires an energy rate value, which will be used for the lifetime
of this strategy. The second parameter is the maximum available power that this power plant
can produce. In this setup file a constant power production of 0.01 kW is assumed, and it is
configured so low in order to validate that the strategy works as expected.
"""


def get_setup(config):
    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    Area('H1 General Load', strategy=LoadHoursStrategy(avg_power_W=200,
                                                                       hrs_per_day=6,
                                                                       hrs_of_day=list(
                                                                           range(12, 20)),
                                                                       acceptable_energy_rate=35),
                         appliance=SwitchableAppliance()),
                    Area('H1 Storage1', strategy=StorageStrategy(initial_capacity=0.6,
                                                                 break_even=(26.99, 27.01),
                                                                 max_abs_battery_power=5.0),
                         appliance=SwitchableAppliance()),
                    Area('H1 Storage2', strategy=StorageStrategy(initial_capacity=0.6,
                                                                 break_even=(26.99, 27.01),
                                                                 max_abs_battery_power=5.0),
                         appliance=SwitchableAppliance()),
                ]
            ),
            Area(
                'House 2',
                [
                    Area('H2 General Load', strategy=LoadHoursStrategy(avg_power_W=200,
                                                                       hrs_per_day=4,
                                                                       hrs_of_day=list(
                                                                           range(12, 20)),
                                                                       acceptable_energy_rate=35),
                         appliance=SwitchableAppliance()),
                    Area('H2 PV', strategy=PVStrategy(4, 80),
                         appliance=PVAppliance()),

                ]
            ),
            Area('Cell Tower', strategy=CellTowerLoadHoursStrategy(avg_power_W=100,
                                                                   hrs_per_day=24,
                                                                   hrs_of_day=list(range(0, 24)),
                                                                   acceptable_energy_rate=35),
                 appliance=SwitchableAppliance()),
            Area('Commercial Energy Producer', strategy=CommercialStrategy(),
                 appliance=SimpleAppliance()
                 ),

        ],
        config=config
    )
    return area
