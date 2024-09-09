# pylint: disable=missing-docstring
from gsy_framework.constants_limits import ConstSettings
from gsy_framework.enums import SpotMarketTypeEnum

from gsy_e.models.area import Market, Asset
from gsy_e.models.strategy.external_strategies.load import LoadHoursForecastExternalStrategy
from gsy_e.models.strategy.external_strategies.pv import PVForecastExternalStrategy
from gsy_e.models.strategy.load_hours import LoadHoursStrategy
from gsy_e.models.strategy.storage import StorageStrategy


def get_setup(config):
    ConstSettings.GeneralSettings.DEFAULT_UPDATE_INTERVAL = 1
    ConstSettings.MASettings.MARKET_TYPE = SpotMarketTypeEnum.TWO_SIDED.value
    ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE = 22

    market = Market(
        "Grid",
        [
            Market(
                "House 1",
                [
                    Asset("H1 General Load", strategy=LoadHoursStrategy(avg_power_W=200,
                                                                        hrs_of_day=list(
                                                                            range(12, 18)),
                                                                        final_buying_rate=35)
                          ),
                    Asset("H1 Storage1", strategy=StorageStrategy(initial_soc=100,
                                                                  battery_capacity_kWh=20)
                          ),
                    Asset("H1 Storage2", strategy=StorageStrategy(initial_soc=100,
                                                                  battery_capacity_kWh=20)
                          ),
                ],
            ),
            Market(
                "House 2",
                [
                    Asset("forecast-measurement-pv",
                          strategy=PVForecastExternalStrategy(
                              panel_count=5, initial_selling_rate=30,
                              final_selling_rate=11, fit_to_limit=True)
                          ),
                    Asset("forecast-measurement-load",
                          strategy=LoadHoursForecastExternalStrategy(
                              final_buying_rate=35, initial_buying_rate=11,
                              use_market_maker_rate=True)
                          ),

                ], external_connection_available=True,
            ),
            Market("Community Load", strategy=LoadHoursStrategy(avg_power_W=100,
                                                                hrs_of_day=list(range(0, 24)),
                                                                final_buying_rate=35)
                   ),
        ],
        config=config
    )
    return market
