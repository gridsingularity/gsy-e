from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.strategy.load_hours_fb import LoadHoursStrategy, CellTowerLoadHoursStrategy
from d3a.models.appliance.pv import PVAppliance
from d3a.setup.jira.test_strategy_custom_pv import CustomPvStrategy

"""
For testing CustomPvStrategy
Apart from the PV in House 2, this setup is equal to setup default_2a
"""


def get_setup(config):
    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    Area('H1 General Load', strategy=LoadHoursStrategy(avg_power_W=200,
                                                                       hrs_per_day=6,
                                                                       hrs_of_day=list(
                                                                           range(12, 18)),
                                                                       max_energy_rate=35),
                         appliance=SwitchableAppliance()),
                    Area('H1 Storage1', strategy=StorageStrategy(initial_capacity_kWh=0.6),
                         appliance=SwitchableAppliance()),
                    Area('H1 Storage2', strategy=StorageStrategy(initial_capacity_kWh=0.6),
                         appliance=SwitchableAppliance()),
                ]
            ),
            Area(
                'House 2',
                [
                    Area('H2 General Load', strategy=LoadHoursStrategy(avg_power_W=200,
                                                                       hrs_per_day=4,
                                                                       hrs_of_day=list(
                                                                           range(12, 16)),
                                                                       max_energy_rate=35),
                         appliance=SwitchableAppliance()),
                    Area('H2 PV', strategy=CustomPvStrategy(4, 80),
                         appliance=PVAppliance()),

                ]
            ),
            Area('Cell Tower', strategy=CellTowerLoadHoursStrategy(avg_power_W=100,
                                                                   hrs_per_day=24,
                                                                   hrs_of_day=list(range(0, 24)),
                                                                   max_energy_rate=35),
                 appliance=SwitchableAppliance())
        ],
        config=config
    )
    return area
