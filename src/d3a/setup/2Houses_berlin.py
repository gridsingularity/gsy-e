
from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
from d3a.models.strategy.predefined_pv import PVUserProfileStrategy
from d3a.models.strategy.predefined_load import DefinedLoadStrategy
from d3a.models.appliance.pv import PVAppliance
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.strategy.predefined_pv import d3a_path
from d3a.models.strategy.commercial_producer import CommercialStrategy
from d3a.models.appliance.simple import SimpleAppliance
import os
from d3a.models.const import ConstSettings

user_profile_path = os.path.join(d3a_path, "resources/PV_Profile_Summer_5kWp.csv")
user_profile_path1 = os.path.join(d3a_path, "resources/House_1.csv")
user_profile_path2 = os.path.join(d3a_path, "resources/House_2.csv")


def get_setup(config):
    ConstSettings.IAASettings.MARKET_TYPE = 2
    area = Area(
        'Grid', [
            Area('House 1', children=[
                Area('Load House 1',
                     strategy=DefinedLoadStrategy(daily_load_profile=user_profile_path1,
                                                  max_energy_rate=35),
                     appliance=SwitchableAppliance()),
                Area('H1 PV1', strategy=PVUserProfileStrategy(power_profile=user_profile_path,
                                                              panel_count=1,
                                                              risk=0,
                                                              min_selling_rate=1),
                     appliance=PVAppliance()),
                Area('H1 Storage1', strategy=StorageStrategy(initial_capacity_kWh=3.2,
                                                             battery_capacity_kWh=6.4,
                                                             max_abs_battery_power_kW=3.3,
                                                             energy_rate_decrease_option=2,
                                                             energy_rate_decrease_per_update=3,
                                                             break_even=(30, 31)
                                                             ),
                     appliance=SwitchableAppliance()),
            ]),
            Area('House 2', children=[
                Area('Load House 2',
                     strategy=DefinedLoadStrategy(daily_load_profile=user_profile_path2,
                                                  max_energy_rate=35),
                     appliance=SwitchableAppliance()),
                Area('H2 PV1', strategy=PVUserProfileStrategy(power_profile=user_profile_path,
                                                              panel_count=1,
                                                              risk=0,
                                                              min_selling_rate=1),
                     appliance=PVAppliance()),
                Area('H2 Storage1', strategy=StorageStrategy(initial_capacity_kWh=3.2,
                                                             battery_capacity_kWh=6.4,
                                                             max_abs_battery_power_kW=3.3,
                                                             energy_rate_decrease_option=2,
                                                             energy_rate_decrease_per_update=3,
                                                             break_even=(30, 31)
                                                             ),
                     appliance=SwitchableAppliance()),
            ]),
            Area('Commercial Energy Producer', strategy=CommercialStrategy(energy_rate=30),
                 appliance=SimpleAppliance()
                 ),
        ],
        config=config
    )
    return area
