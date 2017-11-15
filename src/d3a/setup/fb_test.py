from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.area import Area
from d3a.models.strategy.commercial_producer import CommercialStrategy
from d3a.models.strategy.facebook_device import FacebookDeviceStrategy
from d3a.models.strategy.storage import StorageStrategy


def get_setup(config):
    area = Area(
        'Grid',
        [
            Area('Commercial Energy Producer',
                 strategy=CommercialStrategy(energy_range_wh=(40, 120), energy_price=30),
                 appliance=SimpleAppliance()),
            Area('Storage', strategy=StorageStrategy(initial_capacity=30)),
            Area('TV', strategy=FacebookDeviceStrategy(20, 4, 8)),
            Area('Fridge', strategy=FacebookDeviceStrategy(200, 24, 24 * 7)),
        ],
        config=config
    )
    return area
