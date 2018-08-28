from d3a.models.appliance.pv import PVAppliance
from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
from d3a.models.strategy.commercial_producer import CommercialStrategy
from d3a.models.strategy.pv import PVStrategy
from d3a.models.strategy.load_hours_fb import LoadHoursStrategy
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.strategy.load_hours_fb import CellTowerLoadHoursStrategy


def get_setup(config):
    area = Area(
        'Grid',
        [
            Area(
                'Street 1',
                [
                    Area(
                        'House 1',
                        [
                            Area('H1 General Load 1', strategy=LoadHoursStrategy(avg_power_W=200,
                                                                                 hrs_per_day=23,
                                                                                 hrs_of_day=list(
                                                                                   range(0, 23))),
                                 appliance=SwitchableAppliance()),
                            Area('H1 General Load 2', strategy=LoadHoursStrategy(avg_power_W=500,
                                                                                 hrs_per_day=23,
                                                                                 hrs_of_day=list(
                                                                                   range(0, 23))),
                                 appliance=SwitchableAppliance()),
                        ]
                    ),
                    Area(
                        'House 2',
                        [
                            Area('H2 General Load', strategy=LoadHoursStrategy(avg_power_W=200,
                                                                               hrs_per_day=23,
                                                                               hrs_of_day=list(
                                                                                   range(0, 23))),
                                 appliance=SwitchableAppliance()),
                            Area('H2 PV', strategy=PVStrategy(2, 80),
                                 appliance=PVAppliance()),
                        ]
                    ),
                ]
            ),
            Area(
                'Street 2',
                [
                    Area(
                        'House 3',
                        [
                            Area('H3 Storage', strategy=StorageStrategy(risk=10,
                                                                        initial_capacity=0.6,
                                                                        break_even=(26.99, 27.01),
                                                                        max_abs_battery_power=5.0),
                                 appliance=SwitchableAppliance()),
                        ]
                    ),
                    Area(
                        'House 4',
                        [
                            Area('H4 Storage', strategy=StorageStrategy(risk=10,
                                                                        initial_capacity=0.6,
                                                                        break_even=(26.99, 27.01),
                                                                        max_abs_battery_power=5.0),
                                 appliance=SwitchableAppliance()),
                            Area('H2 General Load', strategy=LoadHoursStrategy(avg_power_W=200,
                                                                               hrs_per_day=23,
                                                                               hrs_of_day=list(
                                                                                   range(0, 23))),
                                 appliance=SwitchableAppliance()),

                        ]
                    ),
                    Area('Commercial Energy Producer',
                         strategy=CommercialStrategy(energy_rate=31),
                         appliance=SimpleAppliance()),
                    Area('Cell Tower', strategy=CellTowerLoadHoursStrategy(avg_power_W=100,
                         hrs_per_day=24, hrs_of_day=list(range(0, 24)), max_energy_rate=30),
                         appliance=SwitchableAppliance())
                ]
            ),
        ],
        config=config
    )
    return area
