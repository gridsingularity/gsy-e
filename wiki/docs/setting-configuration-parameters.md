The following parameters are part of [Simulation Config](https://github.com/gridsingularity/gsy-e/blob/master/src/gsy_e/models/config.py#L33){target=_blank} and are initialised before updating any [ConstSettings](https://github.com/gridsingularity/gsy-framework/blob/master/gsy_framework/constants_limits.py){target=_blank}:

*   sim_duration
*   slot_length
*   tick_length
*   market_maker_rate*
*   grid_fee_pct*
*   grid_fee_const*

In order to update some of these parameters (starred in list above), please use `update_config_parameters` method to update the general configuration parameters in the setup file:

```python
from gsy_framework.constants_limits import ConstSettings
def get_setup(config):
    ConstSettings.MASettings.MARKET_TYPE = 2
    config.update_config_parameters(grid_fee_pct=5,
                                    grid_fee_const=35,
                                    market_maker_rate=30)
    market = Market(
        'Grid',
        [
            Asset('General Load', strategy=LoadHoursStrategy(avg_power_W=200,
                                                             hrs_per_day=4,
                                                             hrs_of_day=list(range(12, 16)),
                                                             final_buying_rate=35)
                  ),
            Asset('PV', strategy=PVStrategy(4, 80)
                  ),
        ],
        config=config
    )
    return market

```
