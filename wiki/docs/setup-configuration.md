##Backend Simulation Configuration

In the backend, the simulation process is slightly different compared to the user interface simulations. There is no need to login to set up a simulation. The user first needs to download the code from our Github Repository (Installation Instructions for [Linux](linux-installation-instructions.md), [Mac](ios-installation-instructions.md) and [Windows](vm-installation-instructions.md)). In the setup-file (in Python programming language), general and [trading strategy](trading-agents-and-strategies) settings can be defined. Examples can be found in the relevant [Grid Singularity GitHub](https://github.com/gridsingularity/gsy-e/tree/master/src/gsy_e/setup){target=_blank} folder.

This is the most basic skeleton for a setup-file:

```python
```python
from gsy_e.models.area import Market
def get_setup(config):
    area = Market("Grid", [])
    return Market
```

The user can add more nested submarkets recursively by adding more instances of `Market` to the second parameter (list) of the `Market` class. To define the strategy of an asset, please use the `Asset` class and its strategy parameter. The following grid architecture is given:

*   Grid
    *   Home 1
        *   H1 General Load
        *   H1 Storage 1
        *   H1 Storage 2
    *   Home 2
        *   H2 General Load

Bold instances in the outline above are markets. For each of these markets, a [market-agent](market-agent.md) is created in the background to execute offer/bid forwarding and matching.

In the following, the corresponding setup-file is shown.

```python
```python
from gsy_e.models.area import Area
from gsy_e.models.strategy.storage import StorageStrategy
from gsy_e.models.strategy.load_hours import LoadHoursStrategy
from gsy_e.models.strategy.pv import PVStrategy


def get_setup(config):
    market = Market(
        'Grid',
        [
            Market(
                'House 1',
                [
                    Asset('H1 General Load', strategy=LoadHoursStrategy(avg_power_W=200,
                                                                        hrs_per_day=6,
                                                                        hrs_of_day=list(
                                                                            range(12, 18)),
                                                                        final_buying_rate=35)
                          ),
                    Asset('H1 Storage1', strategy=StorageStrategy(initial_soc=50)
                          ),
                    Asset('H1 Storage2', strategy=StorageStrategy(initial_soc=50)
                          ),
                ],
                grid_fee_pct=0, grid_fee_const=0,
            ),
            Market(
                'House 2',
                [
                    Asset('H2 General Load', strategy=LoadHoursStrategy(avg_power_W=200,
                                                                        hrs_per_day=4,
                                                                        hrs_of_day=list(
                                                                            range(12, 16)),
                                                                        final_buying_rate=35)
                          ),
                    Asset('H2 PV', strategy=PVStrategy(panel_count=4, initial_selling_rate=30,
                                                       final_selling_rate=5)
                          ),

                ],
                grid_fee_pct=0, grid_fee_const=0,

            ),

        ],
        config=config
    )
    return market
```

Additionally, the user has the possibility to change the default general settings in two different ways:

1. Setup file (best option)
2. gsy-e-setting.json

###Setup file (best option):

The user can overwrite the configuration settings by changing variables of the [ConstSettings](https://github.com/gridsingularity/gsy-framework/blob/master/gsy_framework/constants_limits.py){target=_blank} class in the setup-file. This class defines the default values for various parameters (general simulation settings, market settings and energy asset configuration). For instance, the user can define multiple configuration parameters in the get_setup function by overwriting the[ ConstSettings](https://github.com/gridsingularity/gsy-framework/blob/master/gsy_framework/constants_limits.py){target=_blank} default values. For example, the following parameters can be set :

* Market_type (if equal to 1: [One-Sided Pay-as-Offer](one-sided-pay-as-offer.md), if equal to 2 : [Two-Sided Pay-as-Bid](two-sided-pay-as-bid.md), if equal to 3 : [Two-Sided Pay-as-Clear](two-sided-pay-as-clear.md))
* Grid_fee_type (if equal to 1: [Constant grid fee](constant-fees.md), if equal to 2 : [Percentage grid fee](percentage-fees.md))

Here is an example to setup a simulation with the Two-Sided Pay-as-Bid market type, constant grid fee and default min (0cts/kWh) and max to (35cts/kWh) energy rate for all [loads](model-load.md):

```python
from gsy_framework.constants_limits import ConstSettings
def get_setup(config):
    ConstSettings.MASettings.MARKET_TYPE = 2
    ConstSettings.LoadSettings.MIN_ENERGY_RATE = 0
    ConstSettings.LoadSettings.MAX_ENERGY_RATE = 35
    ConstSettings.MASettings.GRID_FEE_TYPE = 1
```

###gsy-e-settings.json

These general settings can also be parsed via a settings file in JSON format, which contains all constants in the advanced_settings branch. An example can be found here: src/gsy-e/setup/gsy-e-settings.json. The settings JSON file can be parsed via the --settings-file keyword
