from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.appliance.pv import PVAppliance
from d3a.models.strategy.pv import PVStrategy


def get_setup(config):
    from d3a.models.strategy.const import ConstSettings
    ConstSettings.MAX_OFFER_TRAVERSAL_LENGTH = 1
    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    Area('H1 Storage1', strategy=StorageStrategy(risk=0, initial_capacity=0.6,
                                                                 battery_capacity=15.0,
                                                                 break_even=(23.99, 28.01)),
                         appliance=SwitchableAppliance()),
                    Area('H1 Storage2', strategy=StorageStrategy(risk=0, initial_capacity=0.6,
                                                                 battery_capacity=15.0,
                                                                 break_even=(22.99, 28.01)),
                         appliance=SwitchableAppliance()),
                ]
            ),
            Area(
                'House 2',
                [

                    Area('H2 PV', strategy=PVStrategy(1, 0, min_selling_rate=23.0,
                                                      initial_rate_option=2),
                         appliance=PVAppliance()),

                ]
            ),
        ],
        config=config
    )
    return area
