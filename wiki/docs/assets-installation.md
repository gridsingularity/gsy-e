## Solar Panels

There are two options to implement a PV in a backend:

[Solar Profile](https://github.com/gridsingularity/gsy-e/blob/master/src/gsy_e/models/strategy/pv.py) (for template generation profile):
```python
Market(
    "H2 PV",
    strategy=PVStrategy(
        panel_count=4,
        initial_selling_rate=30,
        final_selling_rate=5,
        fit_to_limit=True,
        update_interval=duration(minutes=5)))
```

[User Profile](https://github.com/gridsingularity/gsy-e/blob/master/src/gsy_e/models/strategy/predefined_pv.py) (for uploaded generation profile):
```python
user_profile_path = os.path.join(gsy_e_path, "assets/Solar_Curve_W_sunny.csv")
Market('H1 PV', strategy=PVUserProfileStrategy(power_profile=user_profile_path, panel_count=4))
```

## Consumption

To implement the consumption profile (load) in a backend simulation, two options are available:

[User configure Profile](https://github.com/gridsingularity/gsy-e/blob/master/src/gsy_e/models/strategy/load_hours.py):
```python
Market(
    'Load',
    strategy=LoadHoursStrategy(
        avg_power_W=200, hrs_per_day=6,hrs_of_day=list(range(12, 18)), initial_buying_rate=0,
        final_buying_rate=35))
```

[User upload Profile](https://github.com/gridsingularity/gsy-e/blob/master/src/gsy_e/models/strategy/predefined_load.py):
```python
user_profile_path = os.path.join(gsy_e_path,"assets/load.csv")

Market('Load', strategy=LoadProfileStrategy(daily_load_profile=user_profile_path, initial_buying_rate)
```
### Addendum: `hrs_of_day` and `hrs_per_day`

`hrs_of_day` defines the allowed time-window in which the load has to consume for a time defined by `hrs_per_day`.

For example, a user can input 5 hrs_per_day and give a wider range for hrs_of_day like (2,18). The Load will try to consume as fast as possible during this time if there is any offered energy to purchase within the limits of `initial_buying_rate` and `final_buying_rate` set parameters.
- If there is sufficient energy at affordable rates, the load will consume in the first 5 hours, i.e. from 02:00 until 07:00, with no energy demand unmatched.
- In case energy prices are too high during the time-interval from 04:00 to 16:00, the load will consume from 02:00 until 04:00, turn off, and consume from 16:00 until 18:00, resulting in one hour of energy demand unmatched.

For information on changes in buying and selling rates, please see: [Trading strategies](default-trading-strategy.md)

## Batteries

To implement a battery in a backend simulation one option is available:

[Energy Storage System](https://github.com/gridsingularity/gsy-e/blob/master/src/gsy_e/models/strategy/storage.py)
```python
Market(
    'Storage',
    strategy=StorageStrategy(
        initial_soc=50, energy_rate_decrease_per_update=3, battery_capacity_kWh=1.2,
        max_abs_battery_power_kW=5, final_buying_rate=16.99, final_selling_rate= 17.01))
```

## Power Plant

To implement the power plant in a backend simulation one option is available:

[Finite Power Plant](https://github.com/gridsingularity/gsy-e/blob/master/src/gsy_e/models/strategy/finite_power_plant.py)
```python
profile_kW = {
0: 0.1,
8: 0.15,
12: 0.2,
19: 0.15,
22: 0.1
}
Market(
    "Power Plant",
    strategy=FinitePowerPlant(energy_rate=31.3, max_available_power_kW=profile_kW))
```

## Market Maker
To implement a market maker in a backend simulation, two methods are available :

[Infinite power plant](https://github.com/gridsingularity/gsy-e/blob/master/src/gsy_e/models/strategy/market_maker_strategy.py)
```python
Market('Market Maker', strategy=MarketMakerStrategy(energy_rate=selling_rate, grid_connected=True))
```

[Infinite bus](https://github.com/gridsingularity/gsy-e/blob/master/src/gsy_e/models/strategy/infinite_bus.py)
```python
Market('Market Maker', strategy=InfiniteBusStrategy(energy_buy_rate=22, energy_sell_rate=22))
```

### Addendum: Storage Capacity Based Method.

This method was created to sell energy at lower prices during high state of charge - SOC (when the battery has more energy stored) and at higher prices during low SOC (when the battery can afford to sell its stored energy for less).
If the cap_price_strategy is True, the offer price for the storage is calculated according to:

`offer_rate = initial_selling_rate - ((initial_selling_rate - final_selling_rate)\*soc/100)`

As an example, considering an `initial_selling_rate` of 30 cents/kWh and a `final_selling_rate` of 20 cents/kWh, a storage with an SOC of 1% would sell its energy at 29.9 cents/kWh, and a battery at 100% SOC would sell its energy at 20 cents/kWh.
To implement a power plant in a backend simulation, one option is available:

[Finite Power Plant](https://github.com/gridsingularity/gsy-e/blob/master/src/gsy_e/models/strategy/finite_power_plant.py)

```python
profile_kW = {
    0: 0.1,
    8: 0.15,
    12: 0.2,
    19: 0.15,
    22: 0.1
}
Market("Power Plant", strategy=FinitePowerPlant(energy_rate=31.3, max_available_power_kW=profile_kW))
```
