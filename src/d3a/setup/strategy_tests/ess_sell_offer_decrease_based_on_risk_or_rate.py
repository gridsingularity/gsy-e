from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.strategy.load_hours_fb import LoadHoursStrategy


'''
This setup file is being used to test a house with battery and a general load. StorageStrategy
reduces its unsold offers based on risk/percentage or energy_rate_decrease_per_update.
Based on parameter 'energy_rate_decrease_option' it will take into account either 'risk'
or 'energy_rate_decrease_per_update'
'''


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
                                                                       max_energy_rate=25),
                         appliance=SwitchableAppliance()),
                    Area('H1 Storage1', strategy=StorageStrategy(risk=10,
                                                                 initial_capacity_kWh=5,
                                                                 initial_rate_option=2,
                                                                 energy_rate_decrease_option=1,
                                                                 energy_rate_decrease_per_update=3,
                                                                 battery_capacity_kWh=5,
                                                                 max_abs_battery_power_kW=5,
                                                                 break_even=(16.99, 17.01)),
                         appliance=SwitchableAppliance()),
                ]
            ),
        ],
        config=config
    )
    return area
