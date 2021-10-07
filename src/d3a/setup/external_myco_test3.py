from d3a.models.area import Area
from d3a.models.strategy.external_strategies.load import LoadHoursExternalStrategy
from d3a.models.strategy.external_strategies.pv import PVExternalStrategy
from d3a.models.strategy.external_strategies.storage import StorageExternalStrategy
from d3a_interface.constants_limits import ConstSettings
from d3a_interface.enums import BidOfferMatchAlgoEnum

from d3a.models.strategy.market_maker_strategy import MarketMakerStrategy
from d3a.models.strategy.infinite_bus import InfiniteBusStrategy


# Example of a setup with all the assets in the same market (which is also the Marekt Maker market / highest market level) to avoid problems with propagation

def get_setup(config):
    ConstSettings.IAASettings.MARKET_TYPE = 2
    ConstSettings.IAASettings.BID_OFFER_MATCH_TYPE = (
        BidOfferMatchAlgoEnum.EXTERNAL.value)
    area = Area(
        "Grid",
        [
            Area("H1 General Load1", strategy=LoadHoursExternalStrategy(
                avg_power_W=200, hrs_per_day=6, hrs_of_day=list(range(12, 18)),
                final_buying_rate=35)),
            Area("H1 PV1", strategy=PVExternalStrategy(panel_count=4)),
            Area("H2 General Load1", strategy=LoadHoursExternalStrategy(
                avg_power_W=200, hrs_per_day=24, hrs_of_day=list(range(0, 24)),
                final_buying_rate=35)),
            Area("H2 Storage1", strategy=StorageExternalStrategy(initial_soc=100,
                                                                 battery_capacity_kWh=20)),
            Area("H2 PV", strategy=PVExternalStrategy(panel_count=4)),
            Area("Market Maker",
                 strategy=InfiniteBusStrategy(energy_buy_rate=21, energy_sell_rate=22)),
        ],
        config=config
    )
    return area
