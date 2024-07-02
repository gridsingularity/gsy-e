from gsy_framework.constants_limits import ConstSettings
from gsy_framework.enums import BidOfferMatchAlgoEnum

from gsy_e.models.area import Area
from gsy_e.models.strategy.external_strategies.load import LoadHoursExternalStrategy
from gsy_e.models.strategy.external_strategies.pv import PVExternalStrategy
from gsy_e.models.strategy.external_strategies.storage import StorageExternalStrategy
from gsy_e.models.strategy.market_maker_strategy import MarketMakerStrategy


def get_setup(config):
    ConstSettings.MASettings.MARKET_TYPE = 2
    ConstSettings.MASettings.BID_OFFER_MATCH_TYPE = (
        BidOfferMatchAlgoEnum.EXTERNAL.value)
    area = Area(
        "Grid",
        [
            Area(
                "House 1",
                [
                    Area("H1 General Load1",
                         strategy=LoadHoursExternalStrategy(avg_power_W=200,
                                                            hrs_of_day=list(range(12, 18)),
                                                            final_buying_rate=35)),
                    Area("H1 General Load2",
                         strategy=LoadHoursExternalStrategy(avg_power_W=150,
                                                            hrs_of_day=list(range(0, 24)),
                                                            final_buying_rate=40)),
                    Area("H1 Storage1", strategy=StorageExternalStrategy(initial_soc=100,
                                                                         battery_capacity_kWh=20)),
                    Area("H1 Storage2", strategy=StorageExternalStrategy(initial_soc=100,
                                                                         battery_capacity_kWh=20)),
                    Area("H1 PV1", strategy=PVExternalStrategy(panel_count=4)),
                    Area("H1 PV2", strategy=PVExternalStrategy(panel_count=4)),
                ],
            ),
            Area(
                "House 2",
                [
                    Area("H2 General Load1", strategy=LoadHoursExternalStrategy(
                        avg_power_W=200, hrs_of_day=list(range(0, 24)),
                        final_buying_rate=35)),
                    Area("H2 Storage1", strategy=StorageExternalStrategy(initial_soc=100,
                                                                         battery_capacity_kWh=20)),
                    Area("H2 PV", strategy=PVExternalStrategy(panel_count=4)),

                ],
            ),
            Area("Cell Tower", strategy=LoadHoursExternalStrategy(avg_power_W=100,
                                                                  hrs_of_day=list(range(0, 24)),
                                                                  final_buying_rate=35)
                 ),
            Area("Market Maker",
                 strategy=MarketMakerStrategy(energy_rate=30)

                 ),
        ],
        config=config
    )
    return area
