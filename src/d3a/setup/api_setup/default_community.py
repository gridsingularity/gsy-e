# flake8: noqa

import os
import platform

from d3a.models.area import Area
from d3a_interface.constants_limits import ConstSettings
from d3a.models.strategy.infinite_bus import InfiniteBusStrategy
from d3a.models.strategy.external_strategies.pv import PVUserProfileExternalStrategy
from d3a.models.strategy.external_strategies.load import LoadProfileExternalStrategy
from d3a.models.strategy.external_strategies.storage import StorageExternalStrategy

current_dir = os.path.dirname(__file__)
print(current_dir)
print(platform.python_implementation())


# PV production profile was generated with Energy Data Map https://energydatamap.com/
# Load consumption profiles were generated with Load Profile Generator https://www.loadprofilegenerator.de/


def get_setup(config):

    ConstSettings.GeneralSettings.DEFAULT_UPDATE_INTERVAL = 1
    ConstSettings.IAASettings.MARKET_TYPE = 2
    ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE = 22

    area = Area(
        'Grid',
        [
            Area(
                'Community',
                [
                    Area('Family 2 children+PV',
                         [
                             Area('Load 1 L13', strategy=LoadProfileExternalStrategy(
                                 daily_load_profile=os.path.join(current_dir,
                                                                 "resources/CHR27 Family both at work, 2 children HH1.csv"),
                                 initial_buying_rate=11,
                                 use_market_maker_rate=True),
                                  ),
                             Area('PV 1 (4kW)', strategy=PVUserProfileExternalStrategy(
                                 power_profile=os.path.join(current_dir, "resources/Berlin_pv.csv"),
                                 panel_count=4,
                                 initial_selling_rate=30,
                                 final_selling_rate=11),
                                  ),
                         ]),

                    Area('Family 2 children',
                         [
                             Area('Load 2 L21', strategy=LoadProfileExternalStrategy(
                                 daily_load_profile=os.path.join(current_dir,
                                                                 "resources/CHR44 Family with 2 children, 1 at work, 1 at home HH1.csv"),
                                 initial_buying_rate=11,
                                 use_market_maker_rate=True),
                                  ),
                         ]),

                    Area('Family 3 children+PV+Batt',
                         [
                             Area('Load 3 L17', strategy=LoadProfileExternalStrategy(
                                 daily_load_profile=os.path.join(current_dir,
                                                                 "resources/CHR41 Family with 3 children, both at work HH1.csv"),
                                 initial_buying_rate=11,
                                 use_market_maker_rate=True),
                                  ),
                             Area('PV 3 (5kW)', strategy=PVUserProfileExternalStrategy(
                                 power_profile=os.path.join(current_dir, "resources/Berlin_pv.csv"),
                                 panel_count=5,
                                 initial_selling_rate=30,
                                 final_selling_rate=11),
                                  ),
                             Area('Tesla Powerwall 3', strategy=StorageExternalStrategy(initial_soc=10,
                                                                                        min_allowed_soc=10,
                                                                                        battery_capacity_kWh=14,
                                                                                        max_abs_battery_power_kW=5,
                                                                                        initial_buying_rate=0,
                                                                                        final_buying_rate=25,
                                                                                        initial_selling_rate=30,
                                                                                        final_selling_rate=25.1),
                                  ),
                         ]),

                    Area('Young Couple',
                         [
                             Area('Load 4 L15', strategy=LoadProfileExternalStrategy(
                                 daily_load_profile=os.path.join(current_dir,
                                                                 "resources/CHR33 Couple under 30 years with work HH1.csv"),
                                 initial_buying_rate=11,
                                 use_market_maker_rate=True),
                                  ),
                         ]),

                    Area('Multigenerational house',
                         [
                             Area('Load 5 L9', strategy=LoadProfileExternalStrategy(
                                 daily_load_profile=os.path.join(current_dir,
                                                                 "resources/CHR15 Multigenerational Home working couple, 2 children, 2 seniors HH1.csv"),
                                 initial_buying_rate=11,
                                 use_market_maker_rate=True),
                                  ),
                             Area('PV 5 (10kW)', strategy=PVUserProfileExternalStrategy(
                                 power_profile=os.path.join(current_dir, "resources/Berlin_pv.csv"),
                                 panel_count=10,
                                 initial_selling_rate=30,
                                 final_selling_rate=11),
                                  ),
                             Area('Tesla Powerwall 5', strategy=StorageExternalStrategy(initial_soc=10,
                                                                                        min_allowed_soc=10,
                                                                                        battery_capacity_kWh=14,
                                                                                        max_abs_battery_power_kW=5,
                                                                                        initial_buying_rate=0,
                                                                                        final_buying_rate=25,
                                                                                        initial_selling_rate=30,
                                                                                        final_selling_rate=25.1),
                                  ),
                         ]),

                    Area('Retired couple',
                         [
                             Area('Load 6 L24', strategy=LoadProfileExternalStrategy(
                                 daily_load_profile=os.path.join(current_dir,
                                                                 "resources/CHR54 Retired Couple, no work HH1.csv"),
                                 initial_buying_rate=11,
                                 use_market_maker_rate=True),
                                  ),
                         ]),

                    Area('Flatsharing Student',
                         [
                             Area('Load 7 L22', strategy=LoadProfileExternalStrategy(
                                 daily_load_profile=os.path.join(current_dir,
                                                                 "resources/CHR52 Student Flatsharing HH1.csv"),
                                 initial_buying_rate=11,
                                 use_market_maker_rate=True),
                                  ),
                         ]),

                    Area('6 apartments building',
                         [
                             Area('Load 81 L20', strategy=LoadProfileExternalStrategy(
                                 daily_load_profile=os.path.join(current_dir,
                                                                 "resources/CHR43 Single with 1 child, with work HH1.csv"),
                                 initial_buying_rate=11,
                                 use_market_maker_rate=True),
                                  ),
                             Area('Load 82 L17', strategy=LoadProfileExternalStrategy(
                                 daily_load_profile=os.path.join(current_dir,
                                                                 "resources/CHR39 Couple, 30 - 64 years, with work HH1.csv"),
                                 initial_buying_rate=11,
                                 use_market_maker_rate=True),
                                  ),
                             Area('Load 83 L14', strategy=LoadProfileExternalStrategy(
                                 daily_load_profile=os.path.join(current_dir,
                                                                 "resources/CHR31 Single, Retired HH1.csv"),
                                 initial_buying_rate=11,
                                 use_market_maker_rate=True),
                                  ),
                             Area('Load 84 L10', strategy=LoadProfileExternalStrategy(
                                 daily_load_profile=os.path.join(current_dir,
                                                                 "resources/CHR16 Couple over 65 years HH1.csv"),
                                 initial_buying_rate=11,
                                 use_market_maker_rate=True),
                                  ),
                             Area('Load 85 L22', strategy=LoadProfileExternalStrategy(
                                 daily_load_profile=os.path.join(current_dir,
                                                                 "resources/CHR52 Student Flatsharing HH1.csv"),
                                 initial_buying_rate=11,
                                 use_market_maker_rate=True),
                                  ),
                             Area('Load 86 L8', strategy=LoadProfileExternalStrategy(
                                 daily_load_profile=os.path.join(current_dir, "resources/CHR11 Student, HH1.csv"),
                                 initial_buying_rate=11,
                                 use_market_maker_rate=True),
                                  ),
                         ]),

                    Area('6 apartments building+PV',
                         [
                             Area('Load 81 L20', strategy=LoadProfileExternalStrategy(
                                 daily_load_profile=os.path.join(current_dir,
                                                                 "resources/CHR43 Single with 1 child, with work HH1.csv"),
                                 initial_buying_rate=11,
                                 use_market_maker_rate=True),
                                  ),
                             Area('Load 82 L17', strategy=LoadProfileExternalStrategy(
                                 daily_load_profile=os.path.join(current_dir,
                                                                 "resources/CHR39 Couple, 30 - 64 years, with work HH1.csv"),
                                 initial_buying_rate=11,
                                 use_market_maker_rate=True),
                                  ),
                             Area('Load 83 L14', strategy=LoadProfileExternalStrategy(
                                 daily_load_profile=os.path.join(current_dir,
                                                                 "resources/CHR31 Single, Retired HH1.csv"),
                                 initial_buying_rate=11,
                                 use_market_maker_rate=True),
                                  ),
                             Area('Load 84 L10', strategy=LoadProfileExternalStrategy(
                                 daily_load_profile=os.path.join(current_dir,
                                                                 "resources/CHR16 Couple over 65 years HH1.csv"),
                                 initial_buying_rate=11,
                                 use_market_maker_rate=True),
                                  ),
                             Area('Load 85 L22', strategy=LoadProfileExternalStrategy(
                                 daily_load_profile=os.path.join(current_dir,
                                                                 "resources/CHR52 Student Flatsharing HH1.csv"),
                                 initial_buying_rate=11,
                                 use_market_maker_rate=True),
                                  ),
                             Area('Load 86 L8', strategy=LoadProfileExternalStrategy(
                                 daily_load_profile=os.path.join(current_dir, "resources/CHR11 Student, HH1.csv"),
                                 initial_buying_rate=11,
                                 use_market_maker_rate=True),
                                  ),
                             Area('PV 9 (15kW)', strategy=PVUserProfileExternalStrategy(
                                 power_profile=os.path.join(current_dir, "resources/Berlin_pv.csv"),
                                 panel_count=15,
                                 initial_selling_rate=30,
                                 final_selling_rate=11),
                                  ),
                         ]),

                ], grid_fee_constant=4, external_connection_available=True),

            Area('Market Maker', strategy=InfiniteBusStrategy(energy_buy_rate=21, energy_sell_rate=22)),
        ],
        config=config, grid_fee_constant=4, external_connection_available=True
    )
    return area
