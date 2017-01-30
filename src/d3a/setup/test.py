from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.area import Area
from d3a.models.strategy.commercial_producer import CommercialStrategy


def get_setup(config):
    area = Area(
        'Grid',
        [
            Area('Commercial Energy Producer',
                 strategy=CommercialStrategy(energy_range_wh=(40, 120), energy_price=30),
                 appliance=SimpleAppliance())
        ],
        config=config
    )
    return area
