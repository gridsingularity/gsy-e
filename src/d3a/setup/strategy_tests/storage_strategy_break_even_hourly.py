"""
To validate the break even hourly profile the backend plot Energy Trade Profile Of House 1
is required. The energy rates for the storages are displayed in this plot, and these rates
should adhere to the break even hourly profiles that are defined in this module.
Tip: It's interesting to see the change in results from changing the initial_pv_rate_option
between 1(historical average prices) and 2(market maker price).
"""
from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.strategy.load_hours_fb import LoadHoursStrategy, CellTowerLoadHoursStrategy
from d3a.models.appliance.pv import PVAppliance
from d3a.models.strategy.pv import PVStrategy


# Hourly profiles for the break even points. Index of the dictionary is the hour of day,
# first element is the break even buy price and second element the break even sell price.
# This is the profile for the first battery.
break_even_profile = {
    0: (26.8, 27.1),
    1: (26.8, 27.1),
    2: (26.8, 27.1),
    3: (26.8, 27.1),
    4: (26.8, 27.1),
    5: (26.8, 27.1),
    6: (26.8, 27.1),
    7: (26.8, 27.1),
    8: (24.8, 25.1),
    9: (24.8, 25.1),
    10: (24.8, 25.1),
    11: (24.8, 25.1),
    12: (22.8, 23.1),
    13: (22.8, 23.1),
    14: (22.8, 23.1),
    15: (22.8, 23.1),
    16: (24.8, 25.1),
    17: (24.8, 25.1),
    18: (24.8, 25.1),
    19: (24.8, 25.1),
    20: (26.8, 27.1),
    21: (26.8, 27.1),
    22: (26.8, 27.1),
    23: (26.8, 27.1),
}


# Hourly break even profile for the second battery, displaying the second way for configuring
# the break even profile. Only the hours when there is a price change are recorded. In the
# hours between the keys the break even price remains the same, eg from 00:00 - 9:45 the break
# even price will be (26.5, 27.5), from 10:00-11:45 it will be (24.5, 25.5) and so forth.
break_even_profile_2 = {
    0: (26.5, 27.5),
    10: (24.5, 25.5),
    12: (22.5, 23.5),
    14: (24.5, 25.5),
    18: (26.5, 27.5),
}


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
                                                                           range(12, 18)),
                                                                       max_energy_rate=35),
                         appliance=SwitchableAppliance()),
                    Area('H1 Storage1', strategy=StorageStrategy(risk=10, initial_capacity=0.6,
                                                                 break_even=break_even_profile,
                                                                 max_abs_battery_power=5.0),
                         appliance=SwitchableAppliance()),
                    Area('H1 Storage2', strategy=StorageStrategy(risk=10, initial_capacity=0.6,
                                                                 break_even=break_even_profile_2,
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
                                                                           range(12, 16)),
                                                                       max_energy_rate=35),
                         appliance=SwitchableAppliance()),
                    Area('H2 PV', strategy=PVStrategy(4, 10, initial_rate_option=2),
                         appliance=PVAppliance()),

                ]
            ),
            Area('Cell Tower', strategy=CellTowerLoadHoursStrategy(avg_power_W=100,
                                                                   hrs_per_day=24,
                                                                   hrs_of_day=list(range(0, 24)),
                                                                   max_energy_rate=35),
                 appliance=SwitchableAppliance()),
        ],
        config=config
    )
    return area
