from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.strategy.commercial_producer import CommercialStrategy
from d3a.models.strategy.load_hours_fb import LoadHoursStrategy
from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.appliance.pv import PVAppliance
from d3a.models.strategy.pv import PVStrategy

'''
This setup file is being modified to mimic a typical
modern household having a hybrid PV-ESS system.
Bug: The PV should be selling power cheaper than the Commercial Producer, but it's not selling
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
                                                                       max_energy_rate=14),
                         appliance=SwitchableAppliance()),
                    Area('H1 Storage1', strategy=StorageStrategy(risk=10,
                                                                 initial_capacity_kWh=0.6,
                                                                 initial_rate_option=2,
                                                                 energy_rate_decrease_option=2,
                                                                 energy_rate_decrease_per_update=7,
                                                                 battery_capacity_kWh=1.2,
                                                                 max_abs_battery_power_kW=5,
                                                                 break_even=(12, 17.01)),
                         appliance=SwitchableAppliance()),
                    Area('H1 PV', strategy=PVStrategy(panel_count=4,
                                                      min_selling_rate=5,
                                                      initial_rate_option=2,
                                                      energy_rate_decrease_option=2,
                                                      energy_rate_decrease_per_update=7),
                         appliance=PVAppliance()),

                ]
            ),
            Area('Commercial Energy Producer',
                 strategy=CommercialStrategy(energy_rate=15),
                 appliance=SimpleAppliance()),
        ],
        config=config
    )
    return area
