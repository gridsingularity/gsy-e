from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
from d3a.models.strategy.load_hours_fb import LoadHoursStrategy
from d3a.models.appliance.pv import PVAppliance
from d3a.models.strategy.pv import PVStrategy


"""
This setup file tests the initial market rate options for the PV power plant strategy.
There are 2 available options. 1 stands for using the historical average price as
and initial rate for the PV rates on every market slot. 2 stands for using the market maker rate
for every market slot.
Note: this does not affect the price reduction algorithm that takes place during the market slot.
This option affects the base rate from which the price reduction algorithm will start.
Also note that the market maker rate is used here as an hourly profile.
"""

market_maker_rate = {
    0: 35, 1: 35, 2: 35, 3: 35, 4: 35, 5: 35, 6: 35, 7: 35,
    8: 35, 9: 34, 10: 33, 11: 32, 12: 31, 13: 30, 14: 31,
    15: 32, 16: 33, 17: 34, 18: 35, 19: 35, 20: 35, 21: 35,
    22: 35, 23: 35
}


def get_setup(config):
    config.read_market_maker_rate(market_maker_rate)
    area = Area(
        'Grid',
        [
            Area(
                'House',
                [
                    Area('H1 General Load', strategy=LoadHoursStrategy(
                            avg_power_W=500,
                            hrs_per_day=6,
                            hrs_of_day=list(
                                range(6, 22)),
                            max_energy_rate=35.01
                        ),
                         appliance=SwitchableAppliance()),
                    # The default value is 1, for historical average price
                    # Here a value of 2 is used, which is using the market maker rate
                    Area('H1 PV', strategy=PVStrategy(4, 80, initial_rate_option=2),
                         appliance=PVAppliance()),
                ]
            ),
        ],
        config=config
    )
    return area
