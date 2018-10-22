from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.area import Area
from d3a.models.strategy.commercial_producer import CommercialStrategy
from d3a.models.strategy.permanent import PermanentLoadStrategy
from d3a.models.strategy.pv import PVStrategy
from d3a.models.strategy.storage import StorageStrategy


def get_setup(config):
    area = Area(
        'Grid',
        [
            Area(
                'House',
                [
                    Area('PV', strategy=PVStrategy(10, 50), appliance=SimpleAppliance()),
                    Area('Storage', strategy=StorageStrategy(50), appliance=SimpleAppliance()),
                    Area('Tenant 1', strategy=PermanentLoadStrategy(energy=80),
                         appliance=SimpleAppliance()),
                    Area('Tenant 2', strategy=PermanentLoadStrategy(energy=120),
                         appliance=SimpleAppliance()),
                    Area('Tenant 3', strategy=PermanentLoadStrategy(energy=140),
                         appliance=SimpleAppliance()),
                    Area('Tenant 4', strategy=PermanentLoadStrategy(energy=60),
                         appliance=SimpleAppliance()),
                    Area('Tenant 5', strategy=PermanentLoadStrategy(energy=80),
                         appliance=SimpleAppliance()),
                    Area('Tenant 6', strategy=PermanentLoadStrategy(energy=100),
                         appliance=SimpleAppliance()),
                ]
            ),
            Area('Commercial Energy Producer',
                 strategy=CommercialStrategy(energy_rate=30))
        ],
        config=config
    )
    return area
