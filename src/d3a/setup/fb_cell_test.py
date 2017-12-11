from d3a.models.appliance.pv import PVAppliance
from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.area import Area
from d3a.models.strategy.facebook_device import FacebookDeviceStrategy
from d3a.models.strategy.pv import PVStrategy
from d3a.models.strategy.storage import StorageStrategy


FRACTION_SIZE = 0.005


def get_setup(config):
    area = Area(
        'Grid',
        [
            Area(
                'House1',  # House 1 in a village of 25 houses # Low Lighting, Mobile Charger, TV
                [
                    Area('PV H1', strategy=PVStrategy(5, 40, _offer_fraction_size=FRACTION_SIZE),
                         appliance=PVAppliance()),
                    Area('Lighting H1', strategy=FacebookDeviceStrategy(26.25, 3.5,
                                                                        hrs_of_day=(16, 22)),
                            appliance=SimpleAppliance()),
                    Area('Mobile Charger H1', strategy=FacebookDeviceStrategy(5, 0.33),
                            appliance=SimpleAppliance()),
                ],
            ),
            Area(
                'House2',  # House 1 in a village of 25 houses # Low Lighting, Mobile Charger, TV
                [
                    Area('PV H2', strategy=PVStrategy(5, 40, _offer_fraction_size=FRACTION_SIZE),
                         appliance=PVAppliance()),
                    Area('TV H2', strategy=FacebookDeviceStrategy(50, 4, hrs_of_day=(10, 18)),
                         appliance=SimpleAppliance()),
                    Area('Lighting H2',
                         strategy=FacebookDeviceStrategy(155, 4, hrs_of_day=(15, 23)),
                         appliance=SimpleAppliance()),
                    Area('Storage H2',
                         strategy=StorageStrategy(initial_capacity=0.6,
                                                  _offer_fraction_size=FRACTION_SIZE),
                         appliance=SimpleAppliance()),
                    Area('Mobile Charger H2', strategy=FacebookDeviceStrategy(5, 0.33),
                         appliance=SimpleAppliance()),
                ],
            ),
            Area('Cell Tower', strategy=FacebookDeviceStrategy(100, 24),
                 # The Cell tower is currently programmed as a conventional load
                 appliance=SimpleAppliance()),
        ],
        config=config
    )
    return area
