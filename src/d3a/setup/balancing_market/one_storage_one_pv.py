from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.appliance.pv import PVAppliance
from d3a.models.strategy.pv import PVStrategy
from d3a.device_registry import DeviceRegistry
from d3a.models.strategy.const import ConstSettings


device_registry_dict = {
    "H1 Storage": (32, 35),
}


def get_setup(config):
    DeviceRegistry.REGISTRY = device_registry_dict
    ConstSettings.BALANCING_FLEXIBLE_LOADS_SUPPORT = False
    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    Area('H1 Storage', strategy=StorageStrategy(initial_capacity=6.0,
                                                                battery_capacity=50.0),
                         appliance=SwitchableAppliance()),
                ]
            ),
            Area(
                'House 2',
                [
                    Area('H2 PV',
                         strategy=PVStrategy(4, 0),
                         appliance=PVAppliance()
                         ),

                ]
            ),
        ],
        config=config
    )
    return area
