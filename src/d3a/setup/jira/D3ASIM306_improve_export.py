from d3a.models.appliance.fridge import FridgeAppliance
from d3a.models.appliance.pv import PVAppliance
from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
from d3a.models.strategy.commercial_producer import CommercialStrategy
from d3a.models.strategy.fridge import FridgeStrategy
from d3a.models.strategy.load_hours_fb import LoadHoursStrategy
from d3a.models.strategy.pv import PVStrategy
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.strategy.load_hours_fb import CellTowerLoadHoursStrategy


def get_setup(config):
    area = Area(
        'Grid',
        [
            Area(
                'Street 1',
                [
                    Area(
                        'S1 House 1',
                        [
                            Area('S1 H1 Fridge 1', strategy=FridgeStrategy(10),
                                 appliance=FridgeAppliance()),
                            Area('S1 H1 PV 1', strategy=PVStrategy(2, 10),
                                 appliance=PVAppliance()),
                            Area('S1 H1 Load',
                                 strategy=LoadHoursStrategy(avg_power_W=200,
                                                            hrs_of_day=list(range(0, 24)),
                                                            acceptable_energy_rate=35),
                                 appliance=SwitchableAppliance()),
                            Area('S1 H1 Storage', strategy=StorageStrategy(20),
                                 appliance=SimpleAppliance()),
                        ]
                    ),
                    Area(
                        'S1 House 2',
                        [
                            Area('S1 H3 PV 1', strategy=PVStrategy(2, 10),
                                 appliance=PVAppliance()),
                            Area('S1 H3 PV 2', strategy=PVStrategy(2, 10),
                                 appliance=PVAppliance()),
                            Area('S1 H3 Storage', strategy=StorageStrategy(10),
                                 appliance=SimpleAppliance()),
                        ]
                    ),
                    Area('Cell Tower',
                         strategy=CellTowerLoadHoursStrategy(
                             avg_power_W=100, hrs_per_day=24, hrs_of_day=list(range(0, 24)),
                             acceptable_energy_rate=35), appliance=SwitchableAppliance())
                ]
            ),
            Area(
                'Street 2',
                [
                    Area(
                        'S2 House 1',
                        [
                            Area('S2 H1 Fridge 1', strategy=FridgeStrategy(50),
                                 appliance=FridgeAppliance()),
                            Area('S2 H1 Load 1',
                                 strategy=LoadHoursStrategy(avg_power_W=200,
                                                            hrs_of_day=list(range(0, 24)),
                                                            acceptable_energy_rate=10),
                                 appliance=SimpleAppliance()),
                        ]
                    ),
                    Area(
                        'S2 House 2',
                        [
                            Area('S2 H2 PV', strategy=PVStrategy(2, 10),
                                 appliance=PVAppliance()),
                            Area('S2 H2 Fridge', strategy=FridgeStrategy(50),
                                 appliance=FridgeAppliance()),
                            Area('S2 H2 Load 1',
                                 strategy=LoadHoursStrategy(avg_power_W=200,
                                                            hrs_of_day=list(range(0, 24)),
                                                            acceptable_energy_rate=30),
                                 appliance=SimpleAppliance()),
                            Area('S2 H2 Load 2',
                                 strategy=LoadHoursStrategy(avg_power_W=100,
                                                            hrs_of_day=list(range(10, 20)),
                                                            acceptable_energy_rate=35),
                                 appliance=SimpleAppliance()),
                        ]
                    ),
                ]
            ),
            Area('Commercial Energy Producer',
                 strategy=CommercialStrategy(energy_rate=30),
                 appliance=SimpleAppliance())
        ],
        config=config
    )
    return area
