from d3a.models.appliance.pv import PVAppliance
from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
from d3a.models.strategy.commercial_producer import CommercialStrategy
from d3a.models.strategy.pv import PVStrategy
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
                                                                       hrs_per_day=4,
                                                                       hrs_of_day=(12, 20),
                                                                       acceptable_energy_rate=29),
                         appliance=SwitchableAppliance()),
                    Area('H1 Lighting', strategy=LoadHoursStrategy(avg_power=100,
                                                                   hrs_per_day=4,
                                                                   hrs_of_day=(12, 15)),
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
                                                                       hrs_per_day=3,
                                                                       hrs_of_day=(12, 18),
                                                                       acceptable_energy_rate=50),
                         appliance=SwitchableAppliance()),
                    Area('H2 Lighting', strategy=LoadHoursStrategy(avg_power=100,
                                                                   hrs_per_day=4,
                                                                   hrs_of_day=(12, 15)),
                         appliance=SwitchableAppliance()),
                    Area('H2 PV', strategy=PVStrategy(2, 80),
                         appliance=PVAppliance()),
                ]
            ),
            Area(
                'House 3',
                [
                    Area('H3 General Load', strategy=LoadHoursStrategy(avg_power=100,
                                                                       hrs_per_day=1,
                                                                       hrs_of_day=(12, 13)),
                         appliance=SwitchableAppliance()),
                    Area('H3 Lighting', strategy=LoadHoursStrategy(avg_power=100,
                                                                   hrs_per_day=4,
                                                                   hrs_of_day=(12, 15)),
                         appliance=SwitchableAppliance()),
                    Area('H3 PV', strategy=PVStrategy(4, 60),
                         appliance=PVAppliance()),
                ]
            ),
            Area(
                'House 4',
                [
                    Area('H4 General Load', strategy=LoadHoursStrategy(avg_power=100,
                                                                       hrs_per_day=1,
                                                                       hrs_of_day=(12, 13)),
                         appliance=SwitchableAppliance()),
                    Area('H4 Lighting', strategy=LoadHoursStrategy(avg_power=200,
                                                                   hrs_per_day=4,
                                                                   hrs_of_day=(12, 15)),
                         appliance=SwitchableAppliance()),
                    Area('H4 TV', strategy=LoadHoursStrategy(avg_power=100,
                                                             hrs_per_day=4,
                                                             hrs_of_day=(14, 17)),
                         appliance=SwitchableAppliance()),
                    Area('H4 PV', strategy=PVStrategy(4, 60),
                         appliance=PVAppliance()),
                    Area('H4 Storage1', strategy=StorageStrategy(initial_capacity=0.6),
                         appliance=SwitchableAppliance()),
                    Area('H4 Storage2', strategy=StorageStrategy(initial_capacity=0.6),
                         appliance=SwitchableAppliance()),
                ]
            ),
            Area(
                'House 5',
                [
                    Area('H5 General Load', strategy=LoadHoursStrategy(avg_power=100,
                                                                       hrs_per_day=1,
                                                                       hrs_of_day=(12, 13)),
                         appliance=SwitchableAppliance()),
                    Area('H5 Lighting', strategy=LoadHoursStrategy(avg_power=200,
                                                                   hrs_per_day=4,
                                                                   hrs_of_day=(12, 15)),
                         appliance=SwitchableAppliance()),
                    Area('H5 TV', strategy=LoadHoursStrategy(avg_power=100,
                                                             hrs_per_day=4,
                                                             hrs_of_day=(10, 13)),
                         appliance=SwitchableAppliance()),
                    Area('H5 PV', strategy=PVStrategy(5, 60),
                         appliance=PVAppliance()),
                    Area('H5 Storage1', strategy=StorageStrategy(initial_capacity=0.6),
                         appliance=SwitchableAppliance()),
                    Area('H5 Storage2', strategy=StorageStrategy(initial_capacity=0.6),
                         appliance=SwitchableAppliance()),
                ]
            ),

            Area('Commercial Energy Producer',
                 strategy=CommercialStrategy(energy_range_wh=(40, 120), energy_price=30),
                 appliance=SimpleAppliance()),

            Area('Cell Tower', strategy=LoadHoursStrategy(avg_power=100,
                                                          hrs_per_day=24,
                                                          hrs_of_day=(0, 23)),
                 appliance=SwitchableAppliance())
        ],
        config=config
    )
    return area
