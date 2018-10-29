from d3a.models.appliance.fridge import FridgeAppliance
from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.area import Area
from d3a.models.strategy.fridge import FridgeStrategy
from d3a.models.strategy.storage import StorageStrategy


def get_setup(config):
    area = Area(
        'House',
        [
            Area('Fridge', strategy=FridgeStrategy(), appliance=FridgeAppliance()),
            Area('Storage',
                 strategy=StorageStrategy(initial_capacity_kWh=5.0),
                 appliance=SimpleAppliance())
        ],
        config=config
    )
    return area
