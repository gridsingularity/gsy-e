# from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
# from d3a.models.strategy.commercial_producer import CommercialStrategy
# from d3a.models.strategy.storage import StorageStrategy
from d3a.models.strategy.load_hours_fb import LoadHoursStrategy  # , CellTowerLoadHoursStrategy
from d3a.models.appliance.pv import PVAppliance
from d3a.models.strategy.pv import PVStrategy


def get_setup(config):
    area = Area(
        'Grid',
        [
            Area(
                'House 2',
                [
                    Area('H2 General Load', strategy=LoadHoursStrategy(avg_power_W=200,
                                                                       hrs_per_day=3,
                                                                       hrs_of_day=list(
                                                                           range(10, 20)),
                                                                       acceptable_energy_rate=35),
                         appliance=SwitchableAppliance()),
                    Area('H2 PV', strategy=PVStrategy(15, 80),
                         appliance=PVAppliance()),

                ]
            )
            # Area('Commercial Energy Producer',
            #      strategy=CommercialStrategy(energy_range_wh=(40, 120), energy_price=30),
            #      appliance=SimpleAppliance()
            #      ),

        ],
        config=config
    )
    return area
