## Solar Panels

There are two options to implement a PV in a backend:

[Solar Profile](https://github.com/gridsingularity/gsy-e/blob/master/src/gsy_e/models/strategy/pv.py){target=_blank} (for template generation profile):
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

[User Profile](https://github.com/gridsingularity/gsy-e/blob/master/src/gsy_e/models/strategy/predefined_pv.py){target=_blank} (for uploaded generation profile):
```python
user_profile_path = os.path.join(gsy_e_path, "assets/Solar_Curve_W_sunny.csv")
Market('H1 PV', strategy=PVUserProfileStrategy(power_profile=user_profile_path, panel_count=4))
```

## Consumption

To implement the consumption profile (load) in a backend simulation, two options are available:

[User configure Profile](https://github.com/gridsingularity/gsy-e/blob/master/src/gsy_e/models/strategy/load_hours.py){target=_blank}:
```python
Market(
    'Load',
    strategy=LoadHoursStrategy(
        avg_power_W=200, hrs_per_day=6,hrs_of_day=list(range(12, 18)), initial_buying_rate=0,
        final_buying_rate=35))
```

[User upload Profile](https://github.com/gridsingularity/gsy-e/blob/master/src/gsy_e/models/strategy/predefined_load.py){target=_blank}:
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

[Energy Storage System](https://github.com/gridsingularity/gsy-e/blob/master/src/gsy_e/models/strategy/storage.py){target=_blank}
```python
Market(
    'Storage',
    strategy=StorageStrategy(
        initial_soc=50, energy_rate_decrease_per_update=3, battery_capacity_kWh=1.2,
        max_abs_battery_power_kW=5, final_buying_rate=16.99, final_selling_rate= 17.01))
```

## Power Plant

To implement the power plant in a backend simulation one option is available:

[Finite Power Plant](https://github.com/gridsingularity/gsy-e/blob/master/src/gsy_e/models/strategy/finite_power_plant.py){target=_blank}
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

## Market Maker (Utility Pricing)
To implement a Market Maker in a backend simulation, two methods are available:

[Infinite power plant](https://github.com/gridsingularity/gsy-e/blob/master/src/gsy_e/models/strategy/market_maker_strategy.py){target=_blank} (in this mode, the Market Maker has the ability to meet the infinite energy demand of consumers at the highest rate possible in the grid).
The Market Maker asset strategy in the infinite power plant mode is configured as follows:
```python
Asset('Market Maker', strategy=MarketMakerStrategy(energy_rate, energy_rate_profile, grid_connected))
```
Where _energy_rate_ is the input for a constant buying rate and _energy_rate_profile_ the input for a variable buying rate. With the _grid_connected_ parameter the user can toggle if the asset is connected to the grid or if it should only dictate the highest energy rate in the grid (islanded mode).

[Infinite bus](https://github.com/gridsingularity/gsy-e/blob/master/src/gsy_e/models/strategy/infinite_bus.py){target=_blank} (in this mode, the Market Maker has not only the ability to meet the infinite energy demand of the consumer but can also absorb the infinite generation surplus of prosumers/producers at the lowest rate possible in that grid).
The Market Maker asset strategy in the infinite bus mode is configured as follows:
```python
Asset('Market Maker', strategy=InfiniteBusStrategy(energy_buy_rate, energy_rate_profile, energy_sell_rate, buying_rate_profile))
```
Where _energy_buy_rate_ and _energy_sell_rate_ are inputs for constant rates and _energy_rate_profile_ and _buying_rate_profile_ the inputs for variable rates.

### Addendum: Storage Capacity Based Method.

This method was created to sell energy at lower prices during high state of charge - SOC (when the battery has more energy stored) and at higher prices during low SOC (when the battery can afford to sell its stored energy for less).
If the cap_price_strategy is True, the offer price for the storage is calculated according to:

`offer_rate = initial_selling_rate - ((initial_selling_rate - final_selling_rate)\*soc/100)`

As an example, considering an `initial_selling_rate` of 30 cts/kWh and a `final_selling_rate` of 20 cts/kWh, a storage with an SOC of 1% would sell its energy at 29.9 cts/kWh, and a battery at 100% SOC would sell its energy at 20 cts/kWh.
To implement a power plant in a backend simulation, one option is available:

[Finite Power Plant](https://github.com/gridsingularity/gsy-e/blob/master/src/gsy_e/models/strategy/finite_power_plant.py){target=_blank}

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

### Heat pumps

#### Heat Pump Code Configuration

To configure a heat pump asset (HP) in the backend code, the following lines are to be added to the children's list of one of the areas in the setup file:
```python
Asset(name="Heat Pump", strategy=HeatPumpStrategy())
```

The **HeatPumpStrategy** parameters can be set as follows:

  * **maximum_power_rating_kW**: default=3; the maximal power that the HP will consume;
  * **min_temp_C**: (default=50); minimum temperature of the HP storage. If the temperature drops below this point, the HP buys energy at any cost;
  * **max_temp_C**: (default=60); maximum temperature of the HP storage. If the temperature rises above this point, the HP does not buy any energy;
  * **initial_temp_C**: (default=50); initial temperature of the HP storage at the beginning of the simulation;
  * **external_temp_C_profile**: (mandatory user input); external temperature that influences the efficiency of the HP. If this parameter is selected, the external temperature is constant for the whole simulation run;
  * **tank_volume_l**: (default=50); volume/capacity of the thermal storage tank;
  * **consumption_kWh**: (mandatory user input); amount of energy the heat pump consumes to produce heat, in kWh. Can be provided as a constant energy kWh value or as an energy consumption time-series profile, as a dictionary that follows the supported format;
  * **preferred_buying_rate**: (default=15); rate in cts/kWh that determines the [trading strategy](heat-pump.md#heat-pump-asset-trading-strategy);
  * **source_type**:  set how the heat exchange is conducted, either via air or water/ground, as it determines the COP calculation;
  * **order_updater_parameters**: of type **HeatPumpOrderUpdaterParameters**. A template configuration can be seen [below](#heat-pump-price-strategy-configuration)

#### Heat Pump Price Strategy Configuration

In order to configure the heat pump bid pricing, the **order_updater_parameters**  should be set by assigning the **HeatPumpOrderUpdaterParameters** data class and its parameters to it:

```python
from gsy_e.models.strategy.heat_pump import HeatPumpOrderUpdaterParameters
from pendulum import duration
from gsy_framework.enums import AvailableMarketTypes

Asset(name="Heat Pump", strategy=HeatPumpStrategy(
     order_updater_parameters={
     AvailableMarketTypes.SPOT: HeatPumpOrderUpdaterParameters(
     update_interval=duration(minutes=1), initial_rate=20, final_rate=30)}))
```
The **order_updater_parameters** expects a dictionary with **AvailableMarketTypes** as key and **HeatPumpOrderUpdaterParameters** as values.
If not set by the user, the following default values are used:

  * **update_interval**: interval that represents the time between updates of the bid prices performed by the applied trading strategy (default: 1 minute);
  * **initial_rate**: bid rate at the start of the market slot; default value is the feed-in-tariff rate (if not set, the default value is 0 cts/kWh as explained in table [here](heat-pump.md#parameter-table));
  * **final_rate**: bid rate at the end of the market slot; defined by the infinite bus strategy that is part of the simulation, which is the market maker rate (if not set, the default value is 30 cts/kWh).


#### Virtual Heat Pump Code Configuration

To configure a virtual heat pump asset (VHP) in the Grid Singularity Exchange backend code, the following lines are to be added to the children's list of one of the areas in the setup file:
```python
Asset(name="Virtual Heat Pump", strategy=VirtualHeatPumpStrategy())
```

The **VirtualHeatPumpStrategy** parameters can be set as follows:

  * **maximum_power_rating_kW**: default=3; the maximum power that the VHP will consume
  * **min_temp_C**: (default=50); minimum temperature of the VHP storage. If the temperature drops below this point, the HP buys energy at any cost
  * **max_temp_C**: (default=60); maximum temperature of the VHP storage. If the temperature rises above this point, the HP does not buy any energy
  * **initial_temp_C**: (default=50); initial temperature of the VHP storage
  * **water_supply_temp_C_profile**: (mandatory user input); supply temperature of the water that flows from the district heating network (used to calculate the heat demand of the building)
  * **water_return_temp_C_profile**: (mandatory user input); return temperature of the water that flows from the district heating network (used to calculate the heat demand of the building)
  * **dh_water_flow_m3_profile**: (mandatory user input); water flow from the district heating network, in aggregated cubic metres per market slot (used to calculate the heat demand of the building)
  * **tank_volume_l**: (default=50); volume of the storage tank
  * **calibration_coefficient**: (default=0.65); empirical calibration coefficient for water-to-water heat pumps
  * **preferred_buying_rate**: (default=15); rate in cts/kWh that determines [the trading strategy](heat-pump.md#heat-pump-asset-trading-strategy)
  * **order_updater_parameters**: of type **HeatPumpOrderUpdaterParameters**. A template configuration can be seen [below](#heat-pump-price-strategy-configuration)
