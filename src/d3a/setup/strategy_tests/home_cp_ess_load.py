from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.strategy.commercial_producer import CommercialStrategy
from d3a.models.strategy.load_hours_fb import LoadHoursStrategy
from d3a.models.appliance.simple import SimpleAppliance


'''
This setup file is being modified to mimic a home with load and ess and a commercial producer
The bug here is that the ESS is charging too fast from the commercial producer (it becomes
fully charged in one slot bypassing the max abs battery power
'''


def get_setup(config):
    config.read_market_maker_rate(30)
    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    Area('H1 General Load', strategy=LoadHoursStrategy(avg_power_W=100,
                                                                       hrs_per_day=24,
                                                                       hrs_of_day=list(
                                                                           range(0, 24)),
                                                                       max_energy_rate=25),
                         appliance=SwitchableAppliance()),
                    Area('H1 Storage1', strategy=StorageStrategy(risk=10,
                                                                 initial_capacity_kWh=0.6,
                                                                 initial_rate_option=2,
                                                                 energy_rate_decrease_option=2,
                                                                 energy_rate_decrease_per_update=7,
                                                                 battery_capacity_kWh=1.2,
                                                                 max_abs_battery_power_kW=0.05,
                                                                 break_even=(16, 17.01)),
                         appliance=SwitchableAppliance()),

                ]
            ),
            Area('Commercial Energy Producer',
                 strategy=CommercialStrategy(energy_rate=15),
                 appliance=SimpleAppliance()),
        ],
        config=config
    )
    return area
