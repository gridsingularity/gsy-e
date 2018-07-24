"""
Setup file for displaying the in-finite power plant strategy.
"""

from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
from d3a.models.strategy.load_hours_fb import LoadHoursStrategy
from d3a.models.strategy.commercial_producer import CommercialStrategy
from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.config import SimulationConfig

"""
In-Finite power plant strategy follows the market_maker_rate being passed as
global config parameters. In this setup file, it is intended to validate if
In-Finite power plant trade energy at the pre-defined market_maker_rate.
"""

market_maker_rate = {
    2: 32, 3: 33, 4: 34, 5: 35, 6: 36, 7: 37, 8: 38,
    9: 37, 10: 38, 11: 39, 14: 34, 15: 33, 16: 32,
    17: 31, 18: 30, 19: 31, 20: 31, 21: 31, 22: 29}


def get_setup(config):
    SimulationConfig.read_market_maker_rate(config, market_maker_rate)
    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    Area('H1 General Load', strategy=LoadHoursStrategy(avg_power_W=200,
                                                                       hrs_per_day=23,
                                                                       hrs_of_day=list(
                                                                           range(0, 23))),
                         appliance=SwitchableAppliance()),
                ]
            ),
            Area('Commercial Energy Producer', strategy=CommercialStrategy(),
                 appliance=SimpleAppliance()
                 ),

        ],
        config=config
    )
    return area
