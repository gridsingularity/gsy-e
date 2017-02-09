from d3a.models.appliance.pv import PVAppliance
from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.area import Area
from d3a.models.strategy.permanent import PermanentLoadStrategy
from d3a.models.strategy.pv import PVStrategy


def get_setup(config):
    area = Area(
        'Grid',
        [
            Area('S1 H1 PV 1', strategy=PVStrategy(2, 40),
                 appliance=PVAppliance(panel_count=2)),
            Area('S1 H1 Load 1', strategy=PermanentLoadStrategy(energy=10),
                 appliance=SimpleAppliance()),
            Area('S1 H1 Load 2', strategy=PermanentLoadStrategy(energy=10),
                 appliance=SimpleAppliance()),
            Area('S1 H1 Load 3', strategy=PermanentLoadStrategy(energy=10),
                 appliance=SimpleAppliance()),
            Area('S1 H1 Load 4', strategy=PermanentLoadStrategy(energy=10),
                 appliance=SimpleAppliance()),
            Area('S1 H1 Load 5', strategy=PermanentLoadStrategy(energy=10),
                 appliance=SimpleAppliance()),
            Area('S1 H1 Load 6', strategy=PermanentLoadStrategy(energy=10),
                 appliance=SimpleAppliance()),
        ],
        config=config
    )
    return area
