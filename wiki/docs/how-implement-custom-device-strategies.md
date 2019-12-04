It is possible for the user to overwrite some of the functionalities of the three basic strategies (*PVStrategy*, *StorageStrategy*, *LoadHoursStrategy*).
In order to implement the custom strategies:

1. Go to the desired python file: `d3a/models/strategy/custom_.py`
2. Change the code of the desired functions accordingly by replacing `pass` with the desired functionality. There are example files in `d3a/setup/jira/` named `test_strategy_custom_<device>.py `that are also used for integration tests.

## CustomPvStrategy

The user can change the functionality of the following function of the *PVStrategy* in`d3a/models/strategy/custom_pv.py` :

1. `produced_energy_forecast_kWh`
    - Overwrites `d3a.models.strategy.pv.produced_energy_forecast_kWh` and returns the energy production of the custom PV for each market slot.
    - Is called on every `ACTIVATE` event.
    - Returns dictionary that describes energy production in kWh for each market slot: `self.energy_production_forecast_kW`. Note that the dictionary should have as many entries as the number of market slots.
2. `calculate_initial_sell_rate`
    - Overrides `d3a.models.strategy.update_frequency.calculate_initial_sell_rate`.
    - Is called on every `MARKET_CYCLE` event.
    - Returns the initial value of the sell energy rate for each hour of the simulation.
    - Parameter: `current_time_h`: slot time in hours (e.g. market.time_slot.hour).
3. `decrease_energy_price_over_ticks`
    - Overrides `d3a.models.strategy.update_frequency.decrease_energy_price_over_ticks`.
    - Is called on every `EVENT_TICK` event.
    - Should be used to modify the price decrease over the ticks for the selected market.

## CustomStorageStrategy

The user can change the functionality of the following functions of the *StorageStrategy* in `d3a/setup/jira/test_strategy_custom_storage.py` :

1. `calculate_energy_to_buy`
    - Overrides `d3a.models.strategy.storage.calculate_energy_to_buy`.
    - Is called by `StorageStrategy.buy_energy` and runs on every `EVENT_TICK` event.
    - Clamps to-buy energy to physical or market margins.
    - Returns clamped energy in kWh.
2. `calculate_energy_to_sell`
    - Overrides `d3a.models.strategy.storage.calculate_energy_to_sell`.
    - Is called by `StorageStrategy.sell_energy` and runs on every `EVENT_MARKET_CYCLE` event.
    - Clamps to-sell energy to physical or market margins.
    - Returns clamped energy in kWh.
3. `calculate_selling_rate`
    - Overrides `d3a.models.strategy.storage.calculate_selling_rate`.
    - Is called by `StorageStrategy.sell_energy` and runs on every `EVENT_MARKET_CYCLE` event.
   - Returns initial selling rate in ct./kWh.
4. `decrease_energy_price_over_ticks`
    - Overrides `d3a.models.strategy.update_frequency.decrease_energy_price_over_ticks`.
    - Is called on every `EVENT_TICK` event.
    - Should be used to modify the price decrease over the ticks for the selected market.
5.  `select_market_to_sell`
    - Overrides `d3a.models.strategy.storage.select_market_to_sell`.
    - Is called by `StorageStrategy.sell_energy` and runs on every `EVENT_MARKET_CYCLE` event.
    - Returns target market object.
6. `update_posted_bids`
    - Overwrites `d3a.models.strategy.load_hours_fb.update_posted_bids`.
    - Is called on every `TICK` event.
    - Should be used to modify the price of the bids over the ticks for the selected market. In the default implementation, an increase of the energy over the ticks is implemented.

## CustomLoadStrategy

The user can change the functionality of the following functions of the *LoadHoursStrategy* in `d3a/models/strategy/custom_load.py`:

1. `update_posted_bids`
   - Overwrites `d3a.models.strategy.load_hours_fb.update_posted_bids`.
   - Is called on every `TICK` event.
   - Should be used to modify the price of the bids over the ticks for the selected market. In the default implementation, an increase of the energy over the ticks is implemented.