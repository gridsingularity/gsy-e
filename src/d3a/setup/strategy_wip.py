from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.area import Area
from d3a.models.strategy.commercial_producer import CommercialStrategy
from d3a.models.strategy.fridge import FridgeStrategy
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
                    Area('H1 Fridge1', strategy=FridgeStrategy(20), appliance=SimpleAppliance()),
                    Area('H1 Fridge2', strategy=FridgeStrategy(30), appliance=SimpleAppliance()),
                    Area('H1 Fridge3', strategy=FridgeStrategy(40), appliance=SimpleAppliance()),
                    Area('H1 Fridge4', strategy=FridgeStrategy(50), appliance=SimpleAppliance()),
                    Area('H1 Fridge5', strategy=FridgeStrategy(60), appliance=SimpleAppliance()),
                    Area('H1 Fridge6', strategy=FridgeStrategy(70), appliance=SimpleAppliance()),
                    Area('H1 Fridge7', strategy=FridgeStrategy(80), appliance=SimpleAppliance()),
                    Area('H1 Fridge8', strategy=FridgeStrategy(90), appliance=SimpleAppliance()),
                    Area('H1 Fridge9', strategy=FridgeStrategy(100), appliance=SimpleAppliance()),
                    Area('H1 Storage1', strategy=StorageStrategy(80), appliance=SimpleAppliance()),
                    Area('H1 Storage2', strategy=StorageStrategy(90), appliance=SimpleAppliance()),
                    Area('H1 Storage3', strategy=StorageStrategy(99), appliance=SimpleAppliance()),
                    Area('Commercial Energy Producer', strategy=CommercialStrategy())
                ]
            ),
            Area(
                'House 2',
                [
                    Area('H2 PV1', strategy=PVStrategy(0), appliance=SimpleAppliance()),
                    Area('H2 PV2', strategy=PVStrategy(20), appliance=SimpleAppliance()),
                    Area('H2 PV3', strategy=PVStrategy(30), appliance=SimpleAppliance()),
                    Area('H2 Fridge1', strategy=FridgeStrategy(0), appliance=SimpleAppliance()),
                    Area('H2 Fridge2', strategy=FridgeStrategy(1), appliance=SimpleAppliance()),
                    Area('H2 Fridge3', strategy=FridgeStrategy(10), appliance=SimpleAppliance()),
                    Area('H2 Fridge4', strategy=FridgeStrategy(20), appliance=SimpleAppliance()),
                    Area('H2 Fridge5', strategy=FridgeStrategy(30), appliance=SimpleAppliance()),
                    Area('H2 Fridge6', strategy=FridgeStrategy(40), appliance=SimpleAppliance()),
                    Area('H2 Fridge7', strategy=FridgeStrategy(50), appliance=SimpleAppliance()),
                    Area('H2 Fridge8', strategy=FridgeStrategy(69), appliance=SimpleAppliance()),
                    Area('H2 Storage1', strategy=StorageStrategy(0), appliance=SimpleAppliance()),
                    Area('H2 Storage2', strategy=StorageStrategy(10), appliance=SimpleAppliance()),
                    Area('H2 Storage3', strategy=StorageStrategy(20), appliance=SimpleAppliance()),
                    Area('Commercial Energy Producer', strategy=CommercialStrategy())
                ]
            ),
            Area('Commercial Energy Producer', strategy=CommercialStrategy())
        ],
        config=config
    )
    return area
