"""
Setup file for displaying PVPredefinedStrategy.
"""
from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
from d3a.models.strategy.commercial_producer import CommercialStrategy
from d3a.models.strategy.predefined_load import DefinedLoadStrategy
from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.strategy.predefined_pv import d3a_path
import os
from d3a.models.config import SimulationConfig


"""
DefinedLoadStrategy Strategy requires daily_load_profile and
acceptable_energy_rate is optional.
"""

profile_path = os.path.join(d3a_path, "resources/LOAD_DATA_1.csv")


market_maker_rate = {
    2: 32, 3: 33, 4: 34, 5: 35, 6: 36, 7: 37, 8: 38,
    9: 37, 10: 38, 11: 39, 14: 34, 15: 33, 16: 32,
    17: 31, 18: 30, 19: 31, 20: 31, 21: 31, 22: 29}


def get_setup(config):
    SimulationConfig.read_market_maker_rate(config, market_maker_rate)
    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    Area('H1 DefinedLoad',
                         strategy=DefinedLoadStrategy(daily_load_profile=profile_path,
                                                      acceptable_energy_rate=40),
                         appliance=SwitchableAppliance()),
                ]
            ),
            Area('Commercial Energy Producer', strategy=CommercialStrategy(),
                 appliance=SimpleAppliance()
                 ),
        ],
        config=config
    )
    return area
