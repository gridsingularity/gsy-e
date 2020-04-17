"""
Setup for a microgrid + DSO


"""
import os

from d3a.models.appliance.pv import PVAppliance
from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
from d3a.models.strategy.market_maker_strategy import MarketMakerStrategy
from d3a.models.strategy.predefined_load import DefinedLoadStrategy
from d3a_interface.constants_limits import ConstSettings
from d3a.models.strategy.infinite_bus import InfiniteBusStrategy
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.strategy.load_hours import LoadHoursStrategy
from d3a.models.strategy.predefined_pv import PVUserProfileStrategy

current_dir = os.path.dirname(__file__)


def get_setup(config):

    ConstSettings.GeneralSettings.DEFAULT_UPDATE_INTERVAL = 1
    ConstSettings.IAASettings.MARKET_TYPE = 2
    ConstSettings.GeneralSettings.KEEP_PAST_MARKETS = False
    ConstSettings.IAASettings.MIN_OFFER_AGE = 1

    area = Area(
        'Grid',
        [
            Area(
                'Community',
                [
                    Area(
                        'House 1',
                        [
                            Area('H1 General Load', strategy=DefinedLoadStrategy(
                                daily_load_profile=os.path.join(
                                    current_dir, "../../resources/KPI_L1.csv"),
                                initial_buying_rate=20,
                                final_buying_rate=30,
                                fit_to_limit=True),
                                 appliance=SwitchableAppliance()),
                            Area('H1 PV', strategy=PVUserProfileStrategy(
                                power_profile=os.path.join(
                                    current_dir, "../../resources/KPI_PV1.csv"),
                                initial_selling_rate=20,
                                final_selling_rate=15,
                                fit_to_limit=True),
                                 appliance=PVAppliance()),
                            Area('H1 General Load evening',
                                 strategy=LoadHoursStrategy(
                                     hrs_per_day=1,
                                     hrs_of_day=list([22, 23]),
                                     avg_power_W=2000,
                                     initial_buying_rate=20,
                                     final_buying_rate=30),
                                 appliance=SwitchableAppliance()),
                        ], grid_fee_percentage=0, transfer_fee_const=0,
                    ),
                    Area('central storage', strategy=StorageStrategy(
                        initial_soc=10,
                        min_allowed_soc=10,
                        battery_capacity_kWh=6,
                        max_abs_battery_power_kW=5,
                        initial_buying_rate=12,
                        final_buying_rate=20,
                        initial_selling_rate=29,
                        final_selling_rate=20.01),
                         appliance=SwitchableAppliance()),
                    Area(
                        'House 2',
                        [
                            Area('H2 General Load', strategy=DefinedLoadStrategy(
                                daily_load_profile=os.path.join(
                                    current_dir, "../../resources/KPI_L1.csv"),
                                initial_buying_rate=20,
                                final_buying_rate=30,
                                fit_to_limit=True),
                                 appliance=SwitchableAppliance()),
                            Area('H2 PV', strategy=PVUserProfileStrategy(
                                power_profile=os.path.join(
                                    current_dir, "../../resources/KPI_PV2.csv"),
                                initial_selling_rate=20,
                                final_selling_rate=15,
                                fit_to_limit=True),
                                 appliance=PVAppliance()),
                        ], grid_fee_percentage=0, transfer_fee_const=0,
                    ),
                    Area(
                        'House 3',
                        [
                            Area('H3 General Load', strategy=DefinedLoadStrategy(
                                daily_load_profile=os.path.join(
                                    current_dir, "../../resources/KPI_L1.csv"),
                                initial_buying_rate=20,
                                final_buying_rate=30,
                                fit_to_limit=True),
                                 appliance=SwitchableAppliance()),
                            Area('H3 PV', strategy=PVUserProfileStrategy(
                                power_profile=os.path.join(
                                    current_dir, "../../resources/KPI_PV3.csv"),
                                initial_selling_rate=20,
                                final_selling_rate=15,
                                fit_to_limit=True),
                                 appliance=PVAppliance()),
                        ], grid_fee_percentage=0, transfer_fee_const=0,
                    ),



                ], grid_fee_percentage=0, transfer_fee_const=0,
            ),
            Area('Feed In Tariff', strategy=InfiniteBusStrategy(
                energy_buy_rate=15.2,
                energy_sell_rate=200),
                 appliance=SimpleAppliance()),

            Area('Market Maker',
                 strategy=MarketMakerStrategy(energy_rate=30, grid_connected=True)
                 )
        ],
        config=config, grid_fee_percentage=0, transfer_fee_const=0,
    )
    return area
