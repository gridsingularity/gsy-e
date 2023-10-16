##Scheduled Events

Events need to be defined by the user in the setup files before the start of the simulation, and they are associated with a specific point in time (or duration), at which the event is triggered. An event has to be associated with a market or an asset by using the `event_list` constructor parameter for that Market or Asset class.

There are four different event types, described in further detail below:

*   Add/Remove Market Events
*   Connect/Disconnect Market Events
*   Strategy Events

###Add/Remove Market Events

This event is associated with a market, and dictates that this market (and its submarkets and assets) will be added or removed from the grid at a specific point in time. There are two ways to configure this operation, either via individual events (`EnableMarketEvent` and `DisableMarketEvent`) or by disabling this market for a selected time interval (`DisableIntervalMarketEvent`).

`EnableMarketEvent` / `DisableMarketEvent` commands each accept one argument, which is the hour at which this event is triggered (hourly resolution is supported in the current implementation), and this area will be enabled/disabled at this specific point in time no matter its current state. `DisableIntervalMarketEvent` accepts two arguments, denoting the **start hour** and the **end hour** at which the Market is disabled.

The term _disabled market_ means that the relevant markets and submarkets are not performing any trading, and are hence inactive in the simulation for the time that the market is disabled. Once enabled, the relevant market and its submarkets will start to operate.

Examples for these events are available on the Grid Singularity GitHub:

*   EnableMarketEvent: [isolated_enable_event.py](https://github.com/gridsingularity/gsy-e/blob/master/src/gsy_e/setup/area_events/isolated_enable_event.py){target=_blank}
*   DisableMarketEvent: [isolated_disable_event.py](https://github.com/gridsingularity/gsy-e/blob/master/src/gsy_e/setup/area_events/isolated_disable_event.py){target=_blank}
*   DisableIntervalMarketEvent: [disable_interval_event.py](https://github.com/gridsingularity/gsy-e/blob/master/src/gsy_e/setup/area_events/disable_interval_event.py){target=_blank}

###Connect/Disconnect Market Events

These events are similar to the enable/disable event; both have a similar API and both are used for removing a market from the grid. The difference is that the Connect/Disconnect events are decoupling the relevant submarkets and assets from the main grid. When the event is enabled, there will be two independent grids trading energy internally, but not with each other. This is contrary to enable/disable events, where the subtree is not performing any trades. This can simulate grids that are abruptly decoupled from the main grid, but manage to self-sustain their assets by continuing to trade energy even after they are disconnected from the main grid.

You can find examples for these events on Grid Singularity GitHub:

*   ConnectMarketEvent: [isolated_connect_event.py](https://github.com/gridsingularity/gsy-e/blob/master/src/gsy_e/setup/area_events/isolated_connect_event.py){target=_blank}
*   DisconnectMarketEvent: [isolated_disconnect_event.py](https://github.com/gridsingularity/gsy-e/blob/master/src/gsy_e/setup/area_events/isolated_disconnect_event.py){target=_blank}
*   DisconnectIntervalMarketEvent: [disconnect_interval_event.py](https://github.com/gridsingularity/gsy-e/blob/master/src/gsy_e/setup/area_events/disconnect_interval_event.py){target=_blank}

###Strategy Events

These events are used to change an asset’s trading strategy during the simulation runtime. These are distinct events with no interval event provided.

*   Load StrategyEvent: [load_event.py](https://github.com/gridsingularity/gsy-e/blob/master/src/gsy_e/setup/area_events/load_event.py){target=_blank}
*   PV StrategyEvent: [pv_event.py](https://github.com/gridsingularity/gsy-e/blob/master/src/gsy_e/setup/area_events/pv_event.py){target=_blank}
*   Storage StrategyEvent: [storage_event.py](https://github.com/gridsingularity/gsy-e/blob/master/src/gsy_e/setup/area_events/storage_event.py){target=_blank}
