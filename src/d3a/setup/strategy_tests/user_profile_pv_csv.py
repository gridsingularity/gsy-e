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
from d3a.util import d3a_path
import os


"""
PVUserProfileStrategy Strategy requires power_profile, risk, panel count &
lower selling rate threshold.
"""

user_profile_path = os.path.join(d3a_path, "resources/Solar_Curve_W_sunny.csv")


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
                    Area('H1 PV', strategy=PVUserProfileStrategy(power_profile=user_profile_path,
                                                                 panel_count=1,
                                                                 risk=80),
                         appliance=PVAppliance()),
                ]
            ),
        ],
        config=config
    )
    return area
