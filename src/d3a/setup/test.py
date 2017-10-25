from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.area import Area
from d3a.models.strategy.simple import BuyStrategy, OfferStrategy


def get_setup(config):
    area = Area(
        'Grid',
        [
            Area('bla1', strategy=BuyStrategy(), appliance=SimpleAppliance()),
            Area('bla2', strategy=OfferStrategy(), appliance=SimpleAppliance())
        ],
        config=config
    )
    return area
