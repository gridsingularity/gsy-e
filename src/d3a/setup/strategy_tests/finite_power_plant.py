"""
Setup file for displaying the finite power plant strategy.
"""

from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
from d3a.models.strategy.finite_power_plant import FinitePowerPlant
from d3a.models.strategy.load_hours_fb import LoadHoursStrategy

"""
The finite power plant strategy requires an energy rate value, which will be used for the lifetime
of this strategy. The second parameter is the maximum available power that this power plant
can produce. In this setup file a constant power production of 0.1 kW is assumed, and it is
configured so low in order to validate that the strategy works as expected.
"""


def get_setup(config):
    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    Area('H1 General Load', strategy=LoadHoursStrategy(avg_power_W=500,
                                                                       hrs_per_day=24,
                                                                       hrs_of_day=list(
                                                                           range(0, 24)),
                                                                       max_energy_rate=35),
                         appliance=SwitchableAppliance()),
                ]
            ),
            Area('Finite Commercial Producer',
                 strategy=FinitePowerPlant(energy_rate=31.3, max_available_power_kW=0.1),
                 appliance=SwitchableAppliance()
                 ),

        ],
        config=config
    )
    return area
