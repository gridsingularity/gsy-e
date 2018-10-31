from d3a.models.appliance.pv import PVAppliance
from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
from d3a.models.strategy.commercial_producer import CommercialStrategy
from d3a.models.strategy.predefined_pv import PVPredefinedStrategy
from d3a.models.strategy.electrolyzer import ElectrolyzerStrategy
from d3a.util import d3a_path
import os

electrolizer_profile_file = os.path.join(d3a_path, "resources",
                                         "Electrolyzer_Discharge_Profile_kg.csv")


def get_setup(config):
    area = Area(
        'Grid',
        [
            Area('Electrolyzer', strategy=ElectrolyzerStrategy(
                                          discharge_profile=electrolizer_profile_file,
                                          conversion_factor_kg_to_kWh=50,
                                          reservoir_capacity_kg=56.0,
                                          reservoir_initial_capacity_kg=2.1,
                                          production_rate_kg_h=1.5
                    ), appliance=SwitchableAppliance()),

            Area('PV', strategy=PVPredefinedStrategy(panel_count=1, risk=80),
                 appliance=PVAppliance()),


            Area("Commercial Energy Producer", strategy=CommercialStrategy(),
                 appliance=SwitchableAppliance()),
        ],
        config=config
    )
    return area
