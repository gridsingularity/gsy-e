There are two fees that can be added to every trade in the grid:

- constant transfer fee (in cents/kWh)
- percentage transfer fee (in %) 

In a configuration you can either set constant fees or percentage fees. By default D3A use constant fees. If you want to set percentage fees you just have to add `config.grid_fee_type = 2` at the top of your file.

A percentage transfer fee (in %) or a constant transfer fee (in cents/kWh) can be configured for each area individually in the setup file with the keyword `grid_fee_percentage` and `transfer_fee_const`:

```
Area(
    'House 1',
    [
        Area('H1 General Load', strategy=LoadHoursStrategy(avg_power_W=200,
                                                           hrs_per_day=6,
                                                           final_buying_rate=35),
             appliance=SwitchableAppliance()),
        Area('H1 Storage1', strategy=StorageStrategy(initial_capacity_kWh=0.6),
             appliance=SwitchableAppliance()),
    ],
    grid_fee_percentage=0, transfer_fee_const=2,
),
```

If no `grid_fee_percentage` or `transfer_fee_const` is provided, the global values of `grid_fee_percentage` or `transfer_fee_const` is used (set via the `update_config_parameters` function, see [Setting Global Configuration Parameters](change-global-sim-settings.md))
If none of these is set, the `const.IAASettings.FEE_PERCENTAGE` or `const.IAASettings.FEE_CONSTANT` values are applied to all areas.