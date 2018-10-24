"""
Setup file for displaying LoadHoursStrategy.
"""

from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.area import Area
from d3a.models.strategy.load_hours_fb import LoadHoursStrategy
from d3a.models.strategy.commercial_producer import CommercialStrategy
from d3a.models.strategy.const import ConstSettings


"""
Test parsing of LoadHoursStrategy min_energy_rate as dictionary.
"""

user_profile_int = {
        0: 10,
        6: 15,
        12: 20,
        18: 25,
        21: 30
    }

user_profile_str = "{'00:00': 10, '06:00': 15, '12:00': 20, '18:00': 25, '21:00':30}"


def get_setup(config):
    ConstSettings.IAASettings.MARKET_TYPE = 2
    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    Area('H1 General Load 1',
                         strategy=LoadHoursStrategy(avg_power_W=200, hrs_of_day=list(range(0, 24)),
                                                    min_energy_rate=user_profile_int,
                                                    max_energy_rate=35),
                         appliance=SwitchableAppliance()),
                    Area('H1 General Load 2',
                         strategy=LoadHoursStrategy(avg_power_W=200, hrs_of_day=list(range(0, 24)),
                                                    min_energy_rate=user_profile_str,
                                                    max_energy_rate=35),
                         appliance=SwitchableAppliance()),
                ]
            ),
            Area('Commercial Energy Producer',
                 strategy=CommercialStrategy(energy_rate=9),
                 appliance=SimpleAppliance()
                 ),
        ],
        config=config
    )
    return area
