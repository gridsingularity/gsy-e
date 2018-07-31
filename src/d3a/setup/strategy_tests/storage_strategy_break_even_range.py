from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.strategy.commercial_producer import CommercialStrategy
from d3a.models.strategy.load_hours_fb import LoadHoursStrategy
from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.appliance.pv import PVAppliance
from d3a.models.strategy.pv import PVStrategy


'''
This setup file is being modified to mimic a typical modern household having a hybrid
PV-ESS system.'''


def get_setup(config):
    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    Area('H1 General Load', strategy=LoadHoursStrategy(avg_power_W=200,
                                                                       hrs_per_day=24,
                                                                       hrs_of_day=list(
                                                                           range(0, 24)),
                                                                       acceptable_energy_rate=35),
                         appliance=SwitchableAppliance()),
                    Area('H1 Storage1', strategy=StorageStrategy(risk=10, initial_capacity=0.6,
                                                                 break_even=(26.99, 27.01),
                                                                 max_abs_battery_power=5.0),
                         appliance=SwitchableAppliance()),
                    Area('H1 PV', strategy=PVStrategy(4, 80),
                         appliance=PVAppliance()),

                ]
            ),
            Area('Commercial Energy Producer',
                 strategy=CommercialStrategy(energy_rate=30),
                 appliance=SimpleAppliance()),
        ],
        config=config
    )
    return area
