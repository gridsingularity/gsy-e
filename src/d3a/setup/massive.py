from d3a.models.appliance.fridge import FridgeAppliance
from d3a.models.appliance.pv import PVAppliance
from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
from d3a.models.strategy.commercial_producer import CommercialStrategy
from d3a.models.strategy.e_car import ECarStrategy
from d3a.models.strategy.fridge import FridgeStrategy
from d3a.models.strategy.heatpump import HeatPumpStrategy
from d3a.models.strategy.permanent import PermanentLoadStrategy
from d3a.models.strategy.pv import PVStrategy
from d3a.models.strategy.storage import StorageStrategy


def get_setup(config):
    streets = []
    for s in range(200):
        houses = [
            Area(
                'S{} House {}'.format(s, h),
                [
                    Area('S{} H{} Fridge 1'.format(s, h), strategy=FridgeStrategy(100),
                         appliance=FridgeAppliance()),
                    Area('S{} H{} PV 1'.format(s, h), strategy=PVStrategy(2, 40),
                         appliance=PVAppliance()),
                    Area('S{} H{} Load'.format(s, h), strategy=PermanentLoadStrategy(),
                         appliance=SwitchableAppliance()),
                    Area('S{} H{} Heatpump'.format(s, h), strategy=HeatPumpStrategy(20),
                         appliance=SimpleAppliance()),
                    Area('S{} H{} Storage'.format(s, h), strategy=StorageStrategy(80),
                         appliance=SimpleAppliance()),
                ]
            )
            for h in range(50)

        ]
        streets.append(
            Area(
                'Street {}'.format(s),
                [
                    *houses,
                    Area('S{} ECar'.format(s), strategy=ECarStrategy(arrival_time=None,
                                                                     depart_time=None),
                         appliance=SimpleAppliance()),
                ]
            )
        )

    area = Area(
        'Grid',
        [
            *streets,
            Area('Commercial Energy Producer',
                 strategy=CommercialStrategy(energy_rate=30),
                 appliance=SimpleAppliance())
        ],
        config=config
    )
    return area
