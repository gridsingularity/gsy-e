The user parses the grid architecture and settings to the d3a simulation via a setup-file.
In this setup-file, global and strategy related settings can be set.

Examples can be found in: `d3a/src/d3a/setup/`

This is the most basic skeleton for a setup-file:

```
from d3a.models.area import Area
def get_setup(config):
    area = Area('Grid', [])
    return area
```


Now the user can ad more sub areas recursively by adding more instances of area to the second parameter (list) of the Area class.
If the strategy parameter is set in the Area class, the area is converted to a leaf node, e.g. a load. 
The following grid architecture is given:

- ***Grid***
    - ***House 1***
        - *H1 General Load*
        - *H1 Storage 1*
        - *H1 Storage 2*
    - ***House 2***
        - *H2 General Load*
    - *Cell Tower*

(**Bold** instances are areas, not devices. For each of these non-device areas, an inter-area-agent is created in the background that deals with offer/bid forwarding and matching.)

In the following, the corresponding setup-file is shown.

```
from d3a.models.appliance.switchable import SwitchableAppliance
from d3a.models.area import Area
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.strategy.load_hours import CellTowerLoadHoursStrategy, LoadHoursStrategy
from d3a.models.appliance.pv import PVAppliance
from d3a.models.strategy.pv import PVStrategy
 
 
def get_setup(config):
    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    Area('H1 General Load', strategy=LoadHoursStrategy(avg_power_W=200,
                                                                       hrs_per_day=6,
                                                                       hrs_of_day=list(
                                                                           range(12, 18)),
                                                                       final_buying_rate=35),
                         appliance=SwitchableAppliance()),
                    Area('H1 Storage1', strategy=StorageStrategy(initial_soc=50),
                         appliance=SwitchableAppliance()),
                    Area('H1 Storage2', strategy=StorageStrategy(initial_soc=50),
                         appliance=SwitchableAppliance()),
                ],
                transfer_fee_pct=0, transfer_fee_const=0,
            ),
            Area(
                'House 2',
                [
                    Area('H2 General Load', strategy=LoadHoursStrategy(avg_power_W=200,
                                                                       hrs_per_day=4,
                                                                       hrs_of_day=list(
                                                                           range(12, 16)),
                                                                       final_buying_rate=35),
                         appliance=SwitchableAppliance()),
                    Area('H2 PV', strategy=PVStrategy(panel_count=4, initial_selling_rate=30,
                                                      final_selling_rate=5),
                         appliance=PVAppliance()),
 
                ],
                transfer_fee_pct=0, transfer_fee_const=0,
 
            ),
            Area('Cell Tower', strategy=CellTowerLoadHoursStrategy(avg_power_W=100,
                                                                   hrs_per_day=24,
                                                                   hrs_of_day=list(range(0, 24)),
                                                                   final_buying_rate=35),
                 appliance=SwitchableAppliance()),
        ],
        config=config
    )
    return area
```