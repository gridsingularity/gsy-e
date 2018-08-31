"""
Setup file for displaying PVPredefinedStrategy.
"""
from d3a.models.appliance.pv import PVAppliance
# from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
# from d3a.models.strategy.commercial_producer import CommercialStrategy
from d3a.models.strategy.predefined_pv import PVUserProfileStrategy
# from d3a.models.strategy.storage import StorageStrategy
from d3a.models.strategy.load_hours_fb import LoadHoursStrategy

"""
PVUserProfileStrategy Strategy requires power_profile, risk, panel count &
lower selling rate threshold.
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
        17: 100,
        18: 0
    }


def get_setup(config):
    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    Area('H1 General Load', strategy=LoadHoursStrategy(avg_power_W=500,
                                                                       hrs_per_day=12,
                                                                       hrs_of_day=list(
                                                                           range(7, 20))),
                         appliance=SwitchableAppliance()),
                    Area('H1 PV', strategy=PVUserProfileStrategy(power_profile=user_profile,
                                                                 panel_count=1,
                                                                 risk=80),
                         appliance=PVAppliance()),
                ]
            ),
        ],
        config=config
    )
    return area
