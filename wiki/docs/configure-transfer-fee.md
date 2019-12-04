There are two fees that can be added to every trade in the grid:

- percentage transfer fee (in %) 
- constant transfer fee (in cents/kWh)

The formula for the increased trade price is: `offer/bid_price * (1 + transfer_fee_pct/100 ) + transfer_fee_const`

A percentage transfer fee (in %) and the constant transfer fee (in cents/kWh) can be configured for each area individually in the setup file with the keyword `transfer_fee_pct` and `transfer_fee_const`:

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
    transfer_fee_pct=1, transfer_fee_const=2,
),
```

If no `transfer_fee_pct` or `transfer_fee_const` is provided, the global values of `transfer_fee_pct` or `transfer_fee_const` is used (set via the `update_config_parameters` function, see [Setting Global Configuration Parameters](change-global-sim-settings.md))
If none of these is set, the `const.IAASettings.FEE_PERCENTAGE` or `const.IAASettings.FEE_CONSTANT` values are applied to all areas.