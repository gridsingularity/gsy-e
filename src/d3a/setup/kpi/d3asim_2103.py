import os

from d3a_interface.constants_limits import ConstSettings

from d3a.models.area import Area
from d3a.models.strategy.infinite_bus import InfiniteBusStrategy
from d3a.models.strategy.predefined_load import DefinedLoadStrategy
from d3a.models.strategy.predefined_pv import PVUserProfileStrategy

current_dir = os.path.dirname(__file__)


def get_setup(config):

    ConstSettings.GeneralSettings.DEFAULT_UPDATE_INTERVAL = 1
    ConstSettings.IAASettings.MARKET_TYPE = 1
    ConstSettings.IAASettings.MIN_OFFER_AGE = 0
    ConstSettings.IAASettings.MIN_BID_AGE = 0

    area = Area(
        "Grid",
        [
            Area(
                "Community",
                [
                    Area(
                        "House 1",
                        [
                            Area("H1 General Load",
                                 strategy=DefinedLoadStrategy(
                                     daily_load_profile=os.path.join(current_dir,
                                                                     "../../resources/KPI_L1.csv"),
                                     initial_buying_rate=20,
                                     final_buying_rate=30,
                                     fit_to_limit=True),
                                 ),
                            Area("H1 PV", strategy=PVUserProfileStrategy(
                                power_profile=os.path.join(current_dir,
                                                           "../../resources/KPI_PV1.csv"),
                                initial_selling_rate=20,
                                final_selling_rate=20,
                                fit_to_limit=True),
                                 )
                        ], grid_fee_percentage=0, grid_fee_constant=0,
                    ),
                    Area(
                        "House 2",
                        [
                            Area("H2 General Load", strategy=DefinedLoadStrategy(
                                daily_load_profile=os.path.join(current_dir,
                                                                "../../resources/KPI_L1.csv"),
                                initial_buying_rate=20,
                                final_buying_rate=30,
                                fit_to_limit=True),
                                 ),
                            Area("H2 PV", strategy=PVUserProfileStrategy(
                                power_profile=os.path.join(current_dir,
                                                           "../../resources/KPI_PV2.csv"),
                                initial_selling_rate=20,
                                final_selling_rate=20,
                                fit_to_limit=True),
                                 )
                        ], grid_fee_percentage=0, grid_fee_constant=0,
                    ),
                    Area(
                        "House 3",
                        [
                            Area("H3 General Load", strategy=DefinedLoadStrategy(
                                daily_load_profile=os.path.join(current_dir,
                                                                "../../resources/KPI_L1.csv"),
                                initial_buying_rate=20,
                                final_buying_rate=30,
                                fit_to_limit=True),
                                 ),
                            Area("H3 PV", strategy=PVUserProfileStrategy(
                                power_profile=os.path.join(current_dir,
                                                           "../../resources/KPI_PV3.csv"),
                                initial_selling_rate=20,
                                final_selling_rate=20,
                                fit_to_limit=True),
                                 )
                        ], grid_fee_percentage=0, grid_fee_constant=0,
                    ),



                ], grid_fee_percentage=1, grid_fee_constant=0,
            ),
            Area("DSO", strategy=InfiniteBusStrategy(energy_buy_rate=20, energy_sell_rate=30),
                 )
        ],
        config=config, grid_fee_percentage=0, grid_fee_constant=0,
    )
    return area
