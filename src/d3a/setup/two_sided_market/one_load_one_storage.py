from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.strategy.load_hours_fb import LoadHoursStrategy
from d3a.models.strategy.const import ConstSettings


def get_setup(config):
    # Two sided market
    ConstSettings.INTER_AREA_AGENT_MARKET_TYPE = 2
    ConstSettings.LOAD_MIN_ENERGY_RATE = 15
    ConstSettings.LOAD_MAX_ENERGY_RATE = 35

    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    Area('H1 Storage',
                         strategy=StorageStrategy(initial_capacity=0.6, risk=0),
                         appliance=SwitchableAppliance()),
                ]
            ),
            Area(
                'House 2',
                [
                    Area('H2 General Load', strategy=LoadHoursStrategy(
                        avg_power_W=100,
                        hrs_per_day=10,
                        hrs_of_day=list(range(8, 18)),
                        min_energy_rate=ConstSettings.LOAD_MIN_ENERGY_RATE,
                        max_energy_rate=ConstSettings.LOAD_MAX_ENERGY_RATE
                    ), appliance=SwitchableAppliance()),

                ]
            ),
        ],
        config=config
    )
    return area
