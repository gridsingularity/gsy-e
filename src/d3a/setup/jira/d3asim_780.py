import os
from d3a.d3a_core.util import d3a_path
from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
from d3a.models.strategy.commercial_producer import CommercialStrategy
from d3a.models.strategy.electrolyzer import ElectrolyzerStrategy


discharge_path = os.path.join(d3a_path, "resources/Electrolyzer_Discharge_Profile_kg.csv")


def get_setup(config):
    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    Area('H1 Electrolyser',
                         strategy=ElectrolyzerStrategy(discharge_profile=discharge_path,
                                                       production_rate_kg_h=4.0),
                         appliance=SwitchableAppliance()),
                ]
            ),
            Area('Commercial Energy Producer',
                 strategy=CommercialStrategy(energy_rate=20),
                 appliance=SimpleAppliance()
                 ),

        ],
        config=config
    )
    return area
