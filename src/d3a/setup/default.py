from d3a.models.appliance.pv import PVAppliance
from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
from d3a.models.strategy.load_hours_fb import LoadHoursStrategy
from d3a.models.strategy.pv import PVStrategy
from d3a.models.strategy.storage import StorageStrategy


def get_setup(config):
    area = Area(
        'Grid',
        [
                    Area(
                        'House 1',
                        [
                            Area('H1 General Load',
                                 strategy=LoadHoursStrategy(
                                     avg_power=100,
                                     hrs_per_day=4,
                                     hrs_of_day=(12, 15)
                                 ),
                                 appliance=SwitchableAppliance()),
                            Area('H1 Storage1',
                                 strategy=StorageStrategy(initial_capacity=0.6),
                                 appliance=SwitchableAppliance()
                                 ),
                        ]
                    ),
                    Area(
                        'House 2',
                        [
                            Area('H2 General Load',
                                 strategy=LoadHoursStrategy(
                                     avg_power=100,
                                     hrs_per_day=4,
                                     hrs_of_day=(12, 15)
                                 ),
                                 appliance=SwitchableAppliance()),
                            Area('H2 PV',
                                 strategy=PVStrategy(6, 80),
                                 appliance=PVAppliance()),
                        ]
                    ),
        ],
        config=config
    )
    return area
