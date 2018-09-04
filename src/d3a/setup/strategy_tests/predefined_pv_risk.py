"""
Setup file for displaying PVPredefinedStrategy.
"""
from d3a.models.appliance.pv import PVAppliance
# from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
# from d3a.models.strategy.commercial_producer import CommercialStrategy
from d3a.models.strategy.predefined_pv import PVPredefinedStrategy
# from d3a.models.strategy.storage import StorageStrategy
from d3a.models.strategy.load_hours_fb import LoadHoursStrategy

"""
PredefinedPV Strategy requires risk, panel count, lower selling rate threshold &
cloud_coverage parameters.
Because the risk parameter is required, this is the risk or percentage based PV strategy
There is another setup file in which Faizan has detailed how the risk based strategy works
which will be added
"""


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
                    Area('H1 PV', strategy=PVPredefinedStrategy(panel_count=1,
                                                                risk=80,
                                                                cloud_coverage=2),
                         appliance=PVAppliance()),
                ]
            ),
        ],
        config=config
    )
    return area
