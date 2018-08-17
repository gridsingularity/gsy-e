from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.strategy.commercial_producer import CommercialStrategy
from d3a.models.appliance.simple import SimpleAppliance


'''
This setup file is testing the ESS buy functionality. Right now the ESS is not buying even though
the commercial generator price is below the ESS buy threshold'
'''


def get_setup(config):
    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [

                    Area('H1 Storage1', strategy=StorageStrategy(
                                                                 initial_capacity=2,
                                                                 initial_rate_option=2,
                                                                 energy_rate_decrease_option=2,
                                                                 energy_rate_decrease_per_update=3,
                                                                 battery_capacity=5,
                                                                 max_abs_battery_power=5,
                                                                 break_even=(16.99, 17.01)),
                         appliance=SwitchableAppliance()),
                ]
            ),

            Area('Commercial Energy Producer',
                 strategy=CommercialStrategy(energy_rate=15),
                 appliance=SimpleAppliance()),

        ],
        config=config
    )
    return area
