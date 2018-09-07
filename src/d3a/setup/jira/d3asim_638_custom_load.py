from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
from d3a.models.appliance.pv import PVAppliance
from d3a.models.strategy.pv import PVStrategy
from d3a.setup.jira.test_strategy_custom_load import CustomLoadStrategy
from d3a.models.strategy.const import ConstSettings

"""
For testing CustomLoadStrategy
This setup is equal to two_sided_market.one_pv_one_load and should also return the same results
(only CustomLoadStrategy is used instead of LoadHoursStrategy)
"""


def get_setup(config):
    # Two sided market
    ConstSettings.INTER_AREA_AGENT_MARKET_TYPE = 2
    ConstSettings.MIN_PV_SELLING_RATE = 0
    ConstSettings.DEFAULT_MARKET_MAKER_RATE = 30
    ConstSettings.LOAD_MIN_ENERGY_RATE = 0
    ConstSettings.LOAD_MAX_ENERGY_RATE = 30

    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    Area('H1 General Load', strategy=CustomLoadStrategy(
                        avg_power_W=200,
                        hrs_per_day=6,
                        hrs_of_day=list(range(9, 15)),
                        min_energy_rate=ConstSettings.LOAD_MIN_ENERGY_RATE,
                        max_energy_rate=ConstSettings.LOAD_MAX_ENERGY_RATE
                    ), appliance=SwitchableAppliance()),
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
