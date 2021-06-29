from d3a.models.area import Area
from d3a_interface.constants_limits import ConstSettings
from d3a.models.strategy.infinite_bus import InfiniteBusStrategy
from d3a.models.strategy.load_hours import LoadHoursStrategy
from d3a.models.strategy.pv import PVStrategy
from d3a.models.strategy.finite_power_plant import FinitePowerPlant


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
                    Area('Family 2 children with PV',
                         [
                            Area('Family General Load', strategy=LoadHoursStrategy(
                                avg_power_W=2071, hrs_of_day=list(range(24)), hrs_per_day=24,
                                initial_buying_rate=27.86, final_buying_rate=27.86,
                                fit_to_limit=True)),
                            Area('Family PV', strategy=PVStrategy(
                                max_panel_power_W=17985, panel_count=1,
                                initial_selling_rate=5, final_selling_rate=5))
                         ]),
                    Area('Community PP', strategy=FinitePowerPlant(
                        max_available_power_kW=5, energy_rate=1
                    ))

                ], grid_fee_constant=4.0),
            Area('DSO', strategy=InfiniteBusStrategy(energy_buy_rate=20, energy_sell_rate=22))
        ],
        config=config, grid_fee_constant=4.0,
    )
    return area
