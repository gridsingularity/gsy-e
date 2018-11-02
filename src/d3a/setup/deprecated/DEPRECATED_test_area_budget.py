from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.appliance.pv import PVAppliance
from d3a.models.area import Area
from d3a.models.budget_keeper import BudgetKeeper
from d3a.models.strategy.commercial_producer import CommercialStrategy
from d3a.models.strategy.deprecated.fridge import FridgeStrategy
from d3a.models.strategy.pv import PVStrategy


def get_setup(config):
    area = Area(
        'Grid',
        [
            Area(
                'House1',
                [
                    Area('Fridge1', strategy=FridgeStrategy(80), appliance=SimpleAppliance()),
                    Area('Fridge2', strategy=FridgeStrategy(), appliance=SimpleAppliance()),
                    Area('Fridge3', strategy=FridgeStrategy(50), appliance=SimpleAppliance()),
                    Area('Fridge4', strategy=FridgeStrategy(30), appliance=SimpleAppliance()),
                    Area('Fridge5', strategy=FridgeStrategy(5), appliance=SimpleAppliance()),
                    Area('Fridge6', strategy=FridgeStrategy(), appliance=SimpleAppliance()),
                    Area('Fridge7', strategy=FridgeStrategy(), appliance=SimpleAppliance()),
                    Area('Fridge8', strategy=FridgeStrategy(70), appliance=SimpleAppliance()),
                    Area('PV', strategy=PVStrategy(), appliance=PVAppliance())
                ],
                budget_keeper=BudgetKeeper(500.0, 1)
            ),
            Area('Producer', strategy=CommercialStrategy(), appliance=SimpleAppliance())
        ],
        config=config
    )
    return area
