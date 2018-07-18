"""
Setup file for displaying the finite power plant strategy using a power profile.
"""

from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
from d3a.models.strategy.finite_power_plant import FinitePowerPlant
from d3a.models.strategy.load_hours_fb import LoadHoursStrategy

"""
Power profile for the finite power plant. It will produce 0.01 kW from 00:00-07:45, 0.0015 kW
from 8:00-11:45 and so forth.
"""
diesel_power_profile = {
    0: 100,
    8: 150,
    12: 200,
    19: 150,
    22: 100
}


def get_setup(config):
    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    Area('H1 General Load', strategy=LoadHoursStrategy(avg_power_W=2000,
                                                                       hrs_per_day=24,
                                                                       hrs_of_day=list(
                                                                           range(0, 24)),
                                                                       acceptable_energy_rate=35),
                         appliance=SwitchableAppliance()),
                ]
            ),
            Area('Finite Commercial Producer Profile',
                 strategy=FinitePowerPlant(energy_rate=31.3,
                                           max_available_power=diesel_power_profile),
                 appliance=SwitchableAppliance()
                 ),

        ],
        config=config
    )
    return area
