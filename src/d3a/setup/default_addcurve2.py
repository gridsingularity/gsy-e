# from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
# from d3a.models.strategy.commercial_producer import CommercialStrategy
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.strategy.load_hours_fb import LoadHoursStrategy
# , CellTowerLoadHoursStrategy
from d3a.models.appliance.pv import PVAppliance
from d3a.models.strategy.pv import PVStrategy
from d3a.models.strategy.predef_load import DefinedLoadStrategy
import pathlib


def get_setup(config):
    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    Area('H1 General Load',
                         strategy=DefinedLoadStrategy(
                             path=pathlib.Path(pathlib.Path.cwd(),
                                               'src/d3a/resources/LOAD_DATA_1.csv').expanduser()),
                         # acceptable_energy_rate=35),
                         appliance=SwitchableAppliance()),
                    Area('H1 Storage1', strategy=StorageStrategy(battery_capacity=1.2,
                                                                 initial_charge=50,
                                                                 max_abs_battery_power=1.2),
                         appliance=SwitchableAppliance()),

                ]
            ),
            Area(
                'House 2',
                [
                    Area('H2 General Load', strategy=LoadHoursStrategy(avg_power_W=200,
                                                                       hrs_per_day=1,
                                                                       hrs_of_day=list(
                                                                           range(15, 16))),
                         # acceptable_energy_rate=35),
                         appliance=SwitchableAppliance()),
                    Area('H2 PV', strategy=PVStrategy(2, 80),
                         appliance=PVAppliance()),

                ]
            ),
            # Area('Cell Tower', strategy=CellTowerLoadHoursStrategy(avg_power_W=100,
            #                                                hrs_per_day=24,
            #                                               hrs_of_day=list(range(0, 24)),
            #                                             acceptable_energy_rate=35),
            #  appliance=SwitchableAppliance())
            # Area('Commercial Energy Producer',
            #      strategy=CommercialStrategy(energy_range_wh=(40, 120), energy_price=30),
            #      appliance=SimpleAppliance()
            #      ),

        ],
        config=config
    )
    return area
