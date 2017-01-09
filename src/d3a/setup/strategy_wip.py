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
                    Area('H1 PV', strategy=PVStrategy(), appliance=SimpleAppliance()),
                    Area('H1 Fridge', strategy=FridgeStrategy(), appliance=SimpleAppliance()),
                    Area('H1 Storage', strategy=StorageStrategy(), appliance=SimpleAppliance()),
                    Area('Commercial Energy Producer', strategy=CommercialStrategy())
                ]
            ),
            Area(
                'House 2',
                [
                    Area('H2 PV1', strategy=PVStrategy(0), appliance=SimpleAppliance()),
                    Area('H2 PV3', strategy=PVStrategy(11), appliance=SimpleAppliance()),
                    Area('H2 PV8', strategy=PVStrategy(100), appliance=SimpleAppliance()),
                    Area('H2 Fridge1', strategy=FridgeStrategy(0), appliance=SimpleAppliance()),
                    Area('H2 Fridge2', strategy=FridgeStrategy(80), appliance=SimpleAppliance()),
                    Area('H2 Fridge3', strategy=FridgeStrategy(80), appliance=SimpleAppliance()),
                    Area('H2 Fridge4', strategy=FridgeStrategy(80), appliance=SimpleAppliance()),
                    Area('H2 Fridge5', strategy=FridgeStrategy(80), appliance=SimpleAppliance()),
                    Area('H2 Fridge6', strategy=FridgeStrategy(80), appliance=SimpleAppliance()),
                    Area('H2 Fridge7', strategy=FridgeStrategy(80), appliance=SimpleAppliance()),
                    Area('H2 Fridge8', strategy=FridgeStrategy(80), appliance=SimpleAppliance()),
                    Area('H2 Fridge9', strategy=FridgeStrategy(80), appliance=SimpleAppliance()),
                    Area('H2 Fridge10', strategy=FridgeStrategy(80), appliance=SimpleAppliance()),
                    Area('H2 Fridge11', strategy=FridgeStrategy(80), appliance=SimpleAppliance()),
                    Area('H2 Fridge12', strategy=FridgeStrategy(80), appliance=SimpleAppliance()),
                    Area('H2 Fridge13', strategy=FridgeStrategy(10), appliance=SimpleAppliance()),
                    Area('H2 Storage6', strategy=StorageStrategy(0), appliance=SimpleAppliance()),
                    Area('H2 Storage7', strategy=StorageStrategy(0), appliance=SimpleAppliance()),
                    Area('H2 Storage9', strategy=StorageStrategy(0), appliance=SimpleAppliance()),
                    Area('Commercial Energy Producer', strategy=CommercialStrategy())
                ]
            ),
            Area('Commercial Energy Producer', strategy=CommercialStrategy())
        ],
        config=config
    )
    return area
