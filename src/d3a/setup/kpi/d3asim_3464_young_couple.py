import os

from d3a.models.area import Area
from d3a_interface.constants_limits import ConstSettings
from d3a.models.strategy.infinite_bus import InfiniteBusStrategy
from d3a.models.strategy.load_hours import LoadHoursStrategy
from d3a.models.strategy.pv import PVStrategy


current_dir = os.path.dirname(__file__)


def get_setup(config):

    ConstSettings.IAASettings.MARKET_TYPE = 2
    ConstSettings.IAASettings.MIN_OFFER_AGE = 0
    ConstSettings.IAASettings.MIN_BID_AGE = 0

    area = Area(
        'Grid',
        [
            Area(
                'Community',
                [
                    Area('Young Couple House',
                         [
                            Area('YC General Load', strategy=LoadHoursStrategy(
                                avg_power_W=3147, hrs_of_day=list(range(24)), hrs_per_day=24,
                                initial_buying_rate=30, final_buying_rate=30,
                                fit_to_limit=True)),
                         ]),
                    Area('Community PV', strategy=PVStrategy(
                        max_panel_power_W=4000, panel_count=1,
                        initial_selling_rate=18, final_selling_rate=18)),
                ], grid_fee_constant=4.0),
            Area('DSO', strategy=InfiniteBusStrategy(energy_buy_rate=5, energy_sell_rate=8))
        ],
        config=config, grid_fee_constant=4.0,
    )
    return area
