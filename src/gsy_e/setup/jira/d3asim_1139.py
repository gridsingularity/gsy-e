from gsy_e.models.area import Area
from gsy_e.models.strategy.commercial_producer import CommercialStrategy
from gsy_e.models.strategy.load_hours import LoadHoursStrategy
from gsy_framework.constants_limits import ConstSettings


def get_setup(config):
    market_maker_rate = 3
    ConstSettings.MASettings.MARKET_TYPE = 1
    config.update_config_parameters(market_maker_rate=market_maker_rate)

    houses_1 = [Area(f"House 1 {i}", children=[
        Area(f"House 1 {i} Loads ", strategy=LoadHoursStrategy(avg_power_W=500,
                                                               hrs_of_day=list(range(0, 24)),
                                                               initial_buying_rate=1,
                                                               final_buying_rate=12)
             )])
                for i in range(1, 50)]
    houses_2 = [Area(f"House 2 {i}", children=[
        Area(f"House 2 {i} Loads ",
                strategy=LoadHoursStrategy(avg_power_W=500,
                                           hrs_of_day=list(range(0, 24)),
                                           initial_buying_rate=1,
                                           final_buying_rate=12)
                )])
                for i in range(1, 50)]
    houses_3 = [Area(f"House 3 {i}", children=[
        Area(f"House 3 {i} Loads",
                strategy=LoadHoursStrategy(avg_power_W=500,
                                           hrs_of_day=list(range(0, 24)),
                                           initial_buying_rate=1,
                                           final_buying_rate=12)
                )])
                for i in range(1, 50)]
    flats = [Area(f"Flat {i}", children=[
        Area(f"Flat {i} Loads ",
             strategy=LoadHoursStrategy(avg_power_W=500,
                                        hrs_of_day=list(range(0, 24)),
                                        initial_buying_rate=1,
                                        final_buying_rate=12)
             )])
             for i in range(1, 120)]

    area = Area(
        "Grid", [
            Area("Micro-grid",
                 children=[*houses_1, *houses_2, *houses_3, *flats]),
            Area("Commercial Energy Producer",
                 strategy=CommercialStrategy(energy_rate=market_maker_rate)
                 ),
        ],
        config=config
    )
    return area
