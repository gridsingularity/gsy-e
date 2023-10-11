import os

from gsy_framework.constants_limits import ConstSettings

from gsy_e.gsy_e_core.util import gsye_root_path
from gsy_e.models.area import Area
from gsy_e.models.strategy.virtual_heatpump import VirtualHeatpumpStrategy
from gsy_e.models.strategy.infinite_bus import InfiniteBusStrategy
from gsy_e.models.strategy.pv import PVStrategy

ConstSettings.MASettings.MARKET_TYPE = 2


def get_setup(config):
    area = Area(
        "Grid",
        [
            Area(
                "House 1",
                [
                    Area(
                        "H1 Heat Pump",
                        strategy=VirtualHeatpumpStrategy(
                            maximum_power_rating_kW=10,
                            min_temp_C=20,
                            max_temp_C=70,
                            initial_temp_C=25,
                            tank_volume_l=500,
                            dh_water_flow_m3_profile=os.path.join(
                                gsye_root_path, "resources", "hp_water_flow.csv"),
                            water_supply_temp_C_profile=os.path.join(
                                gsye_root_path, "resources", "hp_supply_temp_C.csv"),
                            water_return_temp_C_profile=os.path.join(
                                gsye_root_path, "resources", "hp_return_temp_C.csv"),
                            preferred_buying_rate=15
                        ),
                    ),
                ],
            ),
            Area(
                "House 2",
                [
                    Area(
                        "H2 PV",
                        strategy=PVStrategy(
                            capacity_kW=0.64,
                            initial_selling_rate=30,
                            final_selling_rate=5,
                        ),
                    ),
                ],
            ),
            Area("Infinite Bus",
                 strategy=InfiniteBusStrategy(energy_sell_rate=25,
                                              energy_buy_rate=0),

                 ),
        ],
        config=config,
    )
    return area
