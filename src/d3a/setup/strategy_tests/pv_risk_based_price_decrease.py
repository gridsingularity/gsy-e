from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
from d3a.models.strategy.load_hours_fb import LoadHoursStrategy
from d3a.models.appliance.pv import PVAppliance
from d3a.models.strategy.pv import PVStrategy


"""
This setup file shows the scenario of PV decreasing its unsold offer based on RISK/percentage.
In this scenario, the risk: 20, initial_pv_rate_option: 2 i.e. based on market_maker_rate.
Load wants to purchase energy for 24hr @ acceptable_energy_rate: 7.01 i,e, load will only buy PV's
energy if its lower than its acceptable_energy_rate.

Considering tick_length = 15s, and max_offer_traversal_length = 10 (in order to propagate
offer from one end to the other extreme end). So, the minimum waiting time for offer update
would be offer_update_wait_time = tick_length * max_offer_traversal_length (15 * 10 = 150s)
Considering, time_slot =  15m -> 900s
The max_possible_offer_update_per_slot = time_slot / offer_update_wait_time (900/150=6)

PV's initial sell offer would 35. To consider max_offer_traversal_length, PV's unsold offer
would be updated 6 time per market slot such that the its final offer would be (35*0.2=7)

Since, the PV can only decrease its unsold offer only 6 times per market slot. And based on risk
its unsold offer final rate should be 7. So, after every update its unsold offer would be decrease
by (35 - 7) / 6 = 4.67


When the the PV offer rate goes as low as 7; only then load will purchase PV's energy.
"""


market_maker_rate = {
    0: 35, 1: 35, 2: 35, 3: 35, 4: 35, 5: 35, 6: 35, 7: 35,
    8: 35, 9: 35, 10: 35, 11: 40, 12: 40, 13: 40, 14: 40,
    15: 35, 16: 35, 17: 35, 18: 35, 19: 35, 20: 35, 21: 35,
    22: 35, 23: 35
}


def get_setup(config):
    config.market_maker_rate = market_maker_rate
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
                            acceptable_energy_rate=7.01
                        ),
                         appliance=SwitchableAppliance()),
                    # The default value is 1, for historical average price
                    # Here a value of 2 is used, which is using the market maker price
                    Area('H1 PV', strategy=PVStrategy(1, 20, initial_pv_rate_option=2),
                         appliance=PVAppliance()),
                ]
            ),
        ],
        config=config
    )
    return area
