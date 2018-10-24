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
    area = Area(
        'Grid',
        [
            Area(
                'Street 1',
                [
                    Area(
                        'S1 House 1',
                        [
                            Area('S1 H1 Fridge 1', strategy=FridgeStrategy(100),
                                 appliance=FridgeAppliance()),
                            Area('S1 H1 PV 1', strategy=PVStrategy(2, 40),
                                 appliance=PVAppliance()),
                            Area('S1 H1 Load', strategy=PermanentLoadStrategy(),
                                 appliance=SwitchableAppliance()),
                            Area('S1 H1 Heatpump', strategy=HeatPumpStrategy(20),
                                 appliance=SimpleAppliance()),
                            Area('S1 H1 Storage', strategy=StorageStrategy(80),
                                 appliance=SimpleAppliance()),
                        ]
                    ),
                    Area(
                        'S1 House 2',
                        [
                            Area('S1 H3 PV 1', strategy=PVStrategy(2, 80),
                                 appliance=PVAppliance()),
                            Area('S1 H3 PV 2', strategy=PVStrategy(1, 30),
                                 appliance=PVAppliance()),
                            Area('S1 H3 PV 3', strategy=PVStrategy(3, 20),
                                 appliance=PVAppliance()),
                            Area('S1 H3 PV 4', strategy=PVStrategy(2, 60),
                                 appliance=PVAppliance()),
                            Area('S1 H3 Storage 1', strategy=StorageStrategy(80),
                                 appliance=SimpleAppliance()),
                            Area('S1 H3 Storage 2', strategy=StorageStrategy(80),
                                 appliance=SimpleAppliance()),
                        ]
                    ),
                    Area(
                        'S1 House 3',
                        [
                            Area('S1 H2 PV', strategy=PVStrategy(1, 60),
                                 appliance=PVAppliance()),
                            Area('S1 H2 Fridge', strategy=FridgeStrategy(50),
                                 appliance=FridgeAppliance()),
                            Area('S1 H2 Load 1', strategy=PermanentLoadStrategy(50),
                                 appliance=SimpleAppliance()),
                            Area('S1 H2 Load 2', strategy=PermanentLoadStrategy(80),
                                 appliance=SimpleAppliance()),
                        ]
                    ),
                    Area('S1 ECar', strategy=ECarStrategy(arrival_time=None, depart_time=None),
                         appliance=SimpleAppliance()),
                ]
            ),
            Area(
                'Street 2',
                [
                    Area(
                        'S2 House 1',
                        [
                            Area('S2 H1 Fridge 1', strategy=FridgeStrategy(50),
                                 appliance=FridgeAppliance()),
                            Area('S2 H1 Fridge 2', strategy=FridgeStrategy(50),
                                 appliance=FridgeAppliance()),
                            Area('S2 H1 Load 1', strategy=PermanentLoadStrategy(50),
                                 appliance=SimpleAppliance()),
                            Area('S2 H1 Load 2', strategy=PermanentLoadStrategy(80),
                                 appliance=SimpleAppliance()),
                        ]
                    ),
                    Area(
                        'S2 House 2',
                        [
                            Area('S2 H2 PV', strategy=PVStrategy(1, 40),
                                 appliance=PVAppliance()),
                            Area('S2 H2 Fridge', strategy=FridgeStrategy(50),
                                 appliance=FridgeAppliance()),
                            Area('S2 H2 Load 1', strategy=PermanentLoadStrategy(50),
                                 appliance=SimpleAppliance()),
                            Area('S2 H2 Load 2', strategy=PermanentLoadStrategy(80),
                                 appliance=SimpleAppliance()),
                            Area('S2 H2 Load 3', strategy=PermanentLoadStrategy(40),
                                 appliance=SimpleAppliance()),
                            Area('S2 H2 Load 4', strategy=PermanentLoadStrategy(10),
                                 appliance=SimpleAppliance()),
                        ]
                    ),
                    Area(
                        'S2 House 3',
                        [
                            Area('S2 H3 PV 1', strategy=PVStrategy(3, 20),
                                 appliance=PVAppliance()),
                            Area('S2 H3 PV 2', strategy=PVStrategy(1, 40),
                                 appliance=PVAppliance()),
                            Area('S2 H3 PV 3', strategy=PVStrategy(1, 80),
                                 appliance=PVAppliance()),
                            Area('S2 H3 Storage', strategy=StorageStrategy(80),
                                 appliance=SimpleAppliance()),
                            Area('S2 H3 Heatpump', strategy=HeatPumpStrategy(0),
                                 appliance=SimpleAppliance()),
                        ]
                    ),
                ]
            ),
            Area('Commercial Energy Producer',
                 strategy=CommercialStrategy(energy_rate=30),
                 appliance=SimpleAppliance())
        ],
        config=config
    )
    return area
