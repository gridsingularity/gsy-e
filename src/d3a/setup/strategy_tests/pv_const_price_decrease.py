from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
from d3a.models.strategy.load_hours_fb import LoadHoursStrategy
from d3a.models.appliance.pv import PVAppliance
from d3a.models.strategy.predefined_pv import PVPredefinedStrategy

"""
This setup file test the PV energy_rate_decrease_per_update i.e. 1 cents/kWh/update
In this case, initial PV offer would be based on market maker rate i.e. 35 cents/kWh

You can expect 5 to 6 updates per market slot (with 15 sec ticks). See below:

Considering tick_length = 15s, and max_offer_traversal_length = 10 (in order to propagate
offer from one end to the other extreme end). So, the minimum waiting time for offer update
would be offer_update_wait_time = tick_length * max_offer_traversal_length (15 * 10 = 150s)
Considering, time_slot =  15m -> 900s
The max_possible_offer_update_per_slot = time_slot / offer_update_wait_time (900/150=6).
However, due to some reason, max_possible_offer_update_per_slot is made one unit less.
Once Spyros is back, it has to be discussed.
"""


market_maker_rate = {
    0: 35, 1: 35, 2: 35, 3: 35, 4: 35, 5: 35, 6: 35, 7: 35,
    8: 35, 9: 35, 10: 35, 11: 35, 12: 35, 13: 35, 14: 35,
    15: 35, 16: 35, 17: 35, 18: 35, 19: 35, 20: 35, 21: 35,
    22: 35, 23: 35
}


def get_setup(config):
    config.read_market_maker_rate(market_maker_rate)
    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    Area('H1 General Load', strategy=LoadHoursStrategy(
                            avg_power_W=500,
                            hrs_per_day=24,
                            hrs_of_day=list(
                                range(0, 24)),
                            max_energy_rate=30.1
                        ),
                         appliance=SwitchableAppliance()),
                    Area('H1 PV', strategy=PVPredefinedStrategy(panel_count=1,
                                                                initial_rate_option=2,
                                                                energy_rate_decrease_per_update=4,
                                                                energy_rate_decrease_option=2,
                                                                cloud_coverage=2),
                         appliance=PVAppliance()),
                ]
            ),
        ],
        config=config
    )
    return area
