"""
Setup file for displaying DefinedLoadStrategy.
"""
from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
from d3a.models.strategy.commercial_producer import CommercialStrategy
from d3a.models.strategy.predefined_load import DefinedLoadStrategy
from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.strategy.predefined_pv import d3a_path
import os


"""
DefinedLoadStrategy Strategy requires daily_load_profile and
max_energy_rate is optional.
"""

profile_path = os.path.join(d3a_path, "resources/LOAD_DATA_1.csv")


def get_setup(config):
    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    Area('H1 DefinedLoad',
                         strategy=DefinedLoadStrategy(daily_load_profile=profile_path,
                                                      max_energy_rate=36),
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
