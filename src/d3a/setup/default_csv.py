# from d3a.models.appliance.simple import SimpleAppliance # NOQA
from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
# from d3a.models.strategy.commercial_producer import CommercialStrategy # NOQA
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.strategy.load_hours_fb import LoadHoursStrategy, CellTowerLoadHoursStrategy
from d3a.models.strategy.predef_load import DefinedLoadStrategy
from d3a.models.appliance.pv import PVAppliance
from d3a.models.strategy.predefined_pv import PVPredefinedStrategy


def get_setup(config):
    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    Area('H1 General Load',
                         strategy=DefinedLoadStrategy(
                             path='/Users/muhammad.faizan/Downloads/LOAD_DATA_1.csv',
                             acceptable_energy_rate=25),
                         appliance=SwitchableAppliance()),
                    Area('H1 Storage1', strategy=StorageStrategy(initial_capacity=0.6),
                         appliance=SwitchableAppliance()),
                    Area('H1 Storage2', strategy=StorageStrategy(initial_capacity=0.6),
                         appliance=SwitchableAppliance()),
                ]
            ),
            Area(
                'House 2',
                [
                    Area('H2 General Load', strategy=LoadHoursStrategy(avg_power=200,
                                                                       hrs_per_day=4,
                                                                       hrs_of_day=(12, 15),
                                                                       acceptable_energy_rate=35),
                         appliance=SwitchableAppliance()),
                    Area('H2 PV', strategy=PVPredefinedStrategy(
                        '/Users/muhammad.faizan/Downloads/PV_DATA_1.csv',
                        90, 5),
                         appliance=PVAppliance()),

                ]
            ),
            Area('Cell Tower', strategy=CellTowerLoadHoursStrategy(avg_power=100,
                                                                   hrs_per_day=24,
                                                                   hrs_of_day=(0, 23),
                                                                   acceptable_energy_rate=35),
                 appliance=SwitchableAppliance())
            # Area('Commercial Energy Producer',
            #      strategy=CommercialStrategy(energy_range_wh=(40, 120), energy_price=30),
            #      appliance=SimpleAppliance()
            #      ),
        ],
        config=config
    )
    return area
