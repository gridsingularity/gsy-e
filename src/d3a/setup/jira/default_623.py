from d3a.models.appliance.pv import PVAppliance
from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
from d3a.models.strategy.load_hours_fb import LoadHoursStrategy
from d3a.models.strategy.predefined_pv import PVPredefinedStrategy

"""

"""


def get_setup(config):
    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    Area('H1 General Load', strategy=LoadHoursStrategy(avg_power_W=200,
                                                                       hrs_per_day=15,
                                                                       hrs_of_day=list(
                                                                           range(5, 20)),
                                                                       max_energy_rate=15),
                         appliance=SwitchableAppliance()),
                    Area('H1 PV', strategy=PVPredefinedStrategy(panel_count=1, risk=50,
                                                                initial_rate_option=2),
                         appliance=PVAppliance()),

                ]
            ),

        ],
        config=config
    )
    return area
