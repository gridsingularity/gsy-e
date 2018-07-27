from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
from d3a.models.strategy.load_hours_fb import LoadHoursStrategy
from d3a.models.appliance.pv import PVAppliance
from d3a.models.strategy.pv import PVStrategy


"""
This setup file test the PV energy_rate_decrease_per_update i.e. 1 cents/kWh/update
In this case, initial PV offer would be based on market maker rate i.e. 35 cents/kWh
"""


market_maker_rate = {
    0: 35, 1: 35, 2: 35, 3: 35, 4: 35, 5: 35, 6: 35, 7: 35,
    8: 35, 9: 35, 10: 35, 11: 35, 12: 35, 13: 35, 14: 35,
    15: 35, 16: 35, 17: 35, 18: 35, 19: 35, 20: 35, 21: 35,
    22: 35, 23: 35
}


def get_setup(config):
    config.market_maker_rate = market_maker_rate
    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    Area('H1 General Load', strategy=LoadHoursStrategy(
                            avg_power_W=500,
                            hrs_per_day=24,
                            hrs_of_day=list(
                                range(0, 24)),
                            acceptable_energy_rate=30.01
                        ),
                         appliance=SwitchableAppliance()),
                    Area('H1 PV', strategy=PVStrategy(panel_count=1,
                                                      initial_pv_rate_option=2,
                                                      energy_rate_decrease_per_update=1,
                                                      energy_rate_decrease_option=2),
                         appliance=PVAppliance()),
                ]
            ),
        ],
        config=config
    )
    return area
