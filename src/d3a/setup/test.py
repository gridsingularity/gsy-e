from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.area import Area
from d3a.models.strategy.simple import BuyStrategy


def get_setup(config):
    area = Area(
        'Grid',
        [
            Area('bla', strategy=BuyStrategy(), appliance=SimpleAppliance())
        ],
        config=config
    )
    return area
