## Editing Configuration Parameters

There are default values (global constants) for configuration parameters, they can be set in the following way:
There are two ways of changing global constants and settings via:

1. `setup-file` (best option)
2. `d3a-settings.json`

### 1. setup-file (best option):

For the global update of configuration please see Setting Global Configuration Parameters section below.

For setting the grid fee please consult [How to configure grid transfer fee](configure-transfer-fee.md).

The user can overwrite the configuration settings by changing the wanted variables of the `ConstSettings` class in the `setup-file`.
For instance, if the user wants to set the market type to double-sided-market, and set the default min and max energy rate for all loads the following lines have to be added to the `get_setup` function:

```
from d3a_interface.constants_limits import ConstSettings
def get_setup(config):
    ConstSettings.IAASettings.MARKET_TYPE = 2
    ConstSettings.LoadSettings.MIN_ENERGY_RATE = 0
    ConstSettings.LoadSettings.MAX_ENERGY_RATE = 35
```



### 2. d3a-settings.json

These global settings can also be parsed via a settings file in JSON format, that contains all constants in the `advanced_settings` branch.
An example can be found here: `src/d3a/setup/d3a-settings.json`
The settings JSON file can be parsed via the `--settings-file` keyword

## Setting Global Configuration Parameters

Following parameters are part of *[SimualtionConfig](https://github.com/gridsingularity/d3a/blob/master/src/d3a/models/config.py#L30)* and are initialised even before updating any *[ConstSettings](change-global-sim-settings.md)*:

- `sim_duration`
- `slot_length`
- `tick_length`
- `market_count`
- `cloud_coverage`\*
- `market_maker_rate`\*
- `transfer_fee_pct`\*
- `transfer_fee_const`\*
- `pv_user_profile`\*
- `max_panel_power_W`

In order to update the some of these parameters (starred in list above), please use `update_config_parameters` method to update the global config parameters in the setup file:

```
def get_setup(config):
    config.update_config_parameters(transfer_fee_pct=5,
                                    transfer_fee_const=35,
                                    cloud_coverage=2,
                                    pv_user_profile="<path>/<profile_name>",
                                    market_maker_rate=30)
   area = Area(
        'Grid',
        [
            Area('General Load', strategy=LoadHoursStrategy(avg_power_W=200,
                                                            hrs_per_day=4,
                                                            hrs_of_day=list(range(12, 16)),
                                                            final_buying_rate=35),
                 appliance=SwitchableAppliance()),
            Area('PV', strategy=PVStrategy(4, 80),
                 appliance=PVAppliance()),
        ],
        config=config
    )
    return area
```