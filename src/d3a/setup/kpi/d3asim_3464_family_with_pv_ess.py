from d3a.models.area import Area
from d3a_interface.constants_limits import ConstSettings
from d3a.models.strategy.infinite_bus import InfiniteBusStrategy
from d3a.models.strategy.load_hours import LoadHoursStrategy
from d3a.models.strategy.pv import PVStrategy
from d3a.models.strategy.storage import StorageStrategy
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
                    Area('Family 2 children with PV + ESS',
                         [
                            Area('Family General Load', strategy=LoadHoursStrategy(
                                avg_power_W=5680, hrs_of_day=list(range(24)), hrs_per_day=24,
                                initial_buying_rate=23, final_buying_rate=23)),
                            Area('Family PV', strategy=PVStrategy(
                                max_panel_power_W=17985, panel_count=1,
                                initial_selling_rate=6, final_selling_rate=6)),
                            Area('Family ESS', strategy=StorageStrategy(
                                 initial_soc=20, battery_capacity_kWh=5,
                                 initial_buying_rate=22.94, final_buying_rate=22.94,
                                 initial_selling_rate=22.95, final_selling_rate=22.95))
                         ]),
                    Area('Community PP', strategy=FinitePowerPlant(
                        max_available_power_kW=10, energy_rate=1
                    )),
                    Area('Community Load', strategy=LoadHoursStrategy(
                        avg_power_W=1200, hrs_of_day=list(range(24)), hrs_per_day=24,
                        initial_buying_rate=10, final_buying_rate=10))

                ], grid_fee_constant=4.0),
            Area('DSO', strategy=InfiniteBusStrategy(energy_buy_rate=20, energy_sell_rate=22))
        ],
        config=config, grid_fee_constant=4.0,
    )
    return area
