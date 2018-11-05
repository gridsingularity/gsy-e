from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.area import Area
from d3a.models.strategy.deprecated.fridge import FridgeStrategy
from d3a.models.strategy.pv import PVStrategy
from d3a.models.strategy.storage import StorageStrategy


def get_setup(config):
    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    Area('H1 PV1', strategy=PVStrategy(80), appliance=SimpleAppliance()),
                    Area('H1 PV2', strategy=PVStrategy(90), appliance=SimpleAppliance()),
                    Area('H1 PV3', strategy=PVStrategy(100), appliance=SimpleAppliance()),
                    Area('H1 PV4', strategy=PVStrategy(100), appliance=SimpleAppliance()),
                    Area('H1 PV5', strategy=PVStrategy(100), appliance=SimpleAppliance()),
                    Area('H1 PV6', strategy=PVStrategy(100), appliance=SimpleAppliance()),
                    Area('H1 PV7', strategy=PVStrategy(100), appliance=SimpleAppliance()),
                    Area('H1 Storage1', strategy=StorageStrategy(80), appliance=SimpleAppliance()),
                    Area('H1 Storage2', strategy=StorageStrategy(90), appliance=SimpleAppliance()),
                    Area('H1 Storage3', strategy=StorageStrategy(99), appliance=SimpleAppliance()),
                ]
            ),
            Area(
                'House 2',
                [
                    Area('H2 Fridge1', strategy=FridgeStrategy(0), appliance=SimpleAppliance()),
                    Area('H2 Fridge2', strategy=FridgeStrategy(1), appliance=SimpleAppliance()),
                    Area('H2 Fridge3', strategy=FridgeStrategy(10), appliance=SimpleAppliance()),
                    Area('H2 Fridge4', strategy=FridgeStrategy(20), appliance=SimpleAppliance()),
                    Area('H2 Fridge5', strategy=FridgeStrategy(30), appliance=SimpleAppliance()),
                    Area('H2 Fridge6', strategy=FridgeStrategy(40), appliance=SimpleAppliance()),
                    Area('H2 Fridge7', strategy=FridgeStrategy(50), appliance=SimpleAppliance()),
                    Area('H2 Fridge8', strategy=FridgeStrategy(69), appliance=SimpleAppliance()),
                ]
            ),
        ],
        config=config
    )
    return area
