from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
from d3a.models.strategy.commercial_producer import CommercialStrategy
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.strategy.load_hours_fb import LoadHoursStrategy


def get_setup(config):
    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    Area('H1 General Load', strategy=LoadHoursStrategy(avg_power=100,
                                                                       hrs_per_day=6,
                                                                       hrs_of_day=(12, 22)),
                         appliance=SwitchableAppliance()),
                    Area('H1 Storage1', strategy=StorageStrategy(initial_capacity=0.6),
                         appliance=SwitchableAppliance()),
                    Area('H1 Storage2', strategy=StorageStrategy(initial_capacity=0.6),
                         appliance=SwitchableAppliance()),
                ]
            ),
            Area(
                'House 2',
                [
                    Area('H2 General Load', strategy=LoadHoursStrategy(avg_power=100,
                                                                       hrs_per_day=4,
                                                                       hrs_of_day=(12, 15)),
                         appliance=SwitchableAppliance()),

                ]
            ),

            Area('Commercial Energy Producer',
                 strategy=CommercialStrategy(energy_range_wh=(40, 120), energy_price=30),
                 appliance=SimpleAppliance()
                 ),

        ],
        config=config
    )
    return area
