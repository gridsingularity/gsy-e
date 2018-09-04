"""
Setup file for displaying DefinedLoadStrategy.
"""
from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.area import Area
from d3a.models.strategy.predefined_load import DefinedLoadStrategy
from d3a.models.strategy.commercial_producer import CommercialStrategy


"""
DefinedLoadStrategy Strategy requires daily_load_profile and
max_energy_rate is optional.
"""

user_profile = {
        8: 100,
        9: 200,
        10: 50,
        11: 80,
        12: 120,
        13: 20,
        14: 70,
        15: 15,
        16: 45,
        17: 100
    }


def get_setup(config):
    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    Area('H1 DefinedLoad',
                         strategy=DefinedLoadStrategy(daily_load_profile=user_profile,
                                                      max_energy_rate=35),
                         appliance=SwitchableAppliance()),
                ]
            ),
            Area('Commercial Energy Producer',
                 strategy=CommercialStrategy(),
                 appliance=SimpleAppliance()
                 ),
        ],
        config=config
    )
    return area
