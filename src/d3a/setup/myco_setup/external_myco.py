import d3a.constants
from d3a.models.area import Area
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.strategy.load_hours import LoadHoursStrategy
from d3a.models.strategy.external_strategies.pv import PVExternalStrategy
from d3a.models.strategy.external_strategies.load import LoadHoursExternalStrategy
from d3a_interface.constants_limits import ConstSettings


def get_setup(config):
    ConstSettings.IAASettings.MARKET_TYPE = 2
    ConstSettings.IAASettings.MIN_BID_AGE = 0
    ConstSettings.IAASettings.BID_OFFER_MATCH_TYPE = \
        d3a.constants.BidOfferMatchAlgoEnum.CUSTOM.value
    ConstSettings.IAASettings.MIN_OFFER_AGE = 0
    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    Area('H1 General Load', strategy=LoadHoursStrategy(avg_power_W=200,
                                                                       hrs_per_day=6,
                                                                       hrs_of_day=list(
                                                                           range(12, 18)),
                                                                       final_buying_rate=35)
                         ),
                    Area('H1 Storage1', strategy=StorageStrategy(initial_soc=100,
                                                                 battery_capacity_kWh=20)
                         ),
                    Area('H1 Storage2', strategy=StorageStrategy(initial_soc=100,
                                                                 battery_capacity_kWh=20)
                         ),
                ],
            ),
            Area(
                'House 2',
                [
                    Area('load', strategy=LoadHoursExternalStrategy(
                        avg_power_W=200, hrs_per_day=24, hrs_of_day=list(range(0, 24)),
                        final_buying_rate=35)
                         ),
                    Area('pv', strategy=PVExternalStrategy(panel_count=4)
                         ),

                ], external_connection_available=True,
            ),
            Area('Cell Tower', strategy=LoadHoursStrategy(avg_power_W=100,
                                                          hrs_per_day=24,
                                                          hrs_of_day=list(range(0, 24)),
                                                          final_buying_rate=35)
                 ),
        ],
        config=config
    )
    return area
