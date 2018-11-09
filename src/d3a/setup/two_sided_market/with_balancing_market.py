from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.strategy.load_hours import LoadHoursStrategy
from d3a.models.const import ConstSettings
from d3a.device_registry import DeviceRegistry


device_registry_dict = {
    "H1 Storage": (32, 35),
    "H2 General Load": (32, 35),
}


def get_setup(config):
    DeviceRegistry.REGISTRY = device_registry_dict
    ConstSettings.BalancingSettings.FLEXIBLE_LOADS_SUPPORT = False
    ConstSettings.BalancingSettings.ENABLE_BALANCING_MARKET = True
    # Two sided market
    ConstSettings.IAASettings.MARKET_TYPE = 2
    ConstSettings.LoadSettings.MIN_ENERGY_RATE = 0
    ConstSettings.LoadSettings.MAX_ENERGY_RATE = 35

    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    Area('H1 Storage',
                         strategy=StorageStrategy(initial_capacity_kWh=10,
                                                  battery_capacity_kWh=12,
                                                  risk=0),
                         appliance=SwitchableAppliance()),
                ]
            ),
            Area(
                'House 2',
                [
                    Area('H2 General Load', strategy=LoadHoursStrategy(
                        avg_power_W=100,
                        hrs_per_day=24,
                        hrs_of_day=list(range(0, 24)),
                        min_energy_rate=ConstSettings.LoadSettings.MIN_ENERGY_RATE,
                        max_energy_rate=ConstSettings.LoadSettings.MAX_ENERGY_RATE
                    ), appliance=SwitchableAppliance()),

                ]
            ),
        ],
        config=config
    )
    return area
