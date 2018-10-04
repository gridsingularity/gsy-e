from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.strategy.load_hours_fb import LoadHoursStrategy
from d3a.device_registry import DeviceRegistry
from d3a.models.strategy.const import ConstSettings


device_registry_dict = {
    "H2 Storage": (42, 45),
    "H1 Load": (46, 47)
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
                    Area('H1 Load', strategy=LoadHoursStrategy(
                        avg_power_W=50,
                        hrs_per_day=24,
                        hrs_of_day=list(range(0, 24)),
                    ), appliance=SwitchableAppliance()),
                ]
            ),
            Area(
                'House 2',
                [
                    Area('H2 Storage', strategy=StorageStrategy(initial_capacity=49.0,
                                                                battery_capacity=50.0),
                         appliance=SwitchableAppliance()),
                ]
            ),
        ],
        config=config
    )
    return area
