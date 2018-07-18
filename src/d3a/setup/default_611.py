from d3a.models.appliance.pv import PVAppliance
# from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
# from d3a.models.strategy.commercial_producer import CommercialStrategy
# from d3a.models.strategy.pv import PVStrategy
# from d3a.models.strategy.storage import StorageStrategy
from d3a.models.strategy.load_hours_fb import LoadHoursStrategy
from d3a.models.strategy.predefined_pv import PVPredefinedStrategy


def get_setup(config):
    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    Area('H1 General Load', strategy=LoadHoursStrategy(avg_power_W=100,
                                                                       hrs_per_day=15,
                                                                       hrs_of_day=list(
                                                                           range(5, 20))),
                         appliance=SwitchableAppliance()),
                    Area('H1 PV1', strategy=PVPredefinedStrategy(panel_count=1, risk=80),
                         appliance=PVAppliance()),
                    Area('H1 PV2', strategy=PVPredefinedStrategy(panel_count=1, risk=80),
                         appliance=PVAppliance()),

                ]
            ),

        ],
        config=config
    )
    return area
