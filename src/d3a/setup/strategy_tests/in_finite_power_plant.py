"""
Setup file for displaying the in-finite power plant strategy.
"""

from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.strategy.load_hours_fb import LoadHoursStrategy, CellTowerLoadHoursStrategy
from d3a.models.strategy.commercial_producer import CommercialStrategy
from d3a.models.appliance.simple import SimpleAppliance

"""
In-Finite power plant strategy follows the market_maker_rate being passed as
global config parameters. In this setup file, it is intended to validate if
In-Finite power plant trade energy at the pre-defined market_maker_rate.
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
