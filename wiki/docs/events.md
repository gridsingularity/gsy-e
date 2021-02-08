The user has the ability to modify the modelling setup while the simulated network is running. These modifications are termed **events**. To create an event the user can either go to the `Modelling` page and make a change while the simulation is running or pause the simulation beforehand (by clicking `pause` on the [Results page](results.md)), resuming once changes are implemented.

Possible events are :

*   **Add** or **delete** markets and energy assets
*   **Change parameters** of energy assets (with the exception of their names and the [Market Maker](model-market-maker.md))
*   **Change market configuration** settings (except names)

##Events in Simulations run using the User Interface

Once an event is set, the user can track it on the timeline displayed at the top of the simulation. If the user clicks on the event on the Modelling page, the grid setup at that specific time is viewed. If the user clicks on an event in the Results page, the results of the specific markets and energy assets are viewed.

![alt_text](images/image1.png "image_tooltip")

![alt_text](images/image2.png "image_tooltip")
 whenever a market or energy asset was added

![alt_text](images/image3.png "image_tooltip")
 whenever a market or energy asset parameter was modified

![alt_text](images/image4.png "image_tooltip")
 whenever a market or energy asset was removed

![alt_text](images/image5.png "image_tooltip")
 whenever multiple events have been executed at the same time

##Events in Simulations run using the Backend

In a [backend](https://github.com/gridsingularity/d3a) simulation, events need to be defined by the user in the setup files before the start of the simulation, and they are associated with a specific point in time (or duration), at which the event is triggered. An event has to be associated with a market by using the `event_list` constructor parameter for that market.

There are four different event types, described in further detail below:

*   Add/Remove Market Events
*   Connect/Disconnect Market Events
*   Strategy Events
*   Configuration Events 

###Add/Remove Market Events

This event is associated with a market, and dictates that this market (and its submarkets and assets) will be added or removed from the grid at a specific point in time. There are two ways to configure this operation, either via individual events (`EnableMarketEvent` and `DisableMarketEvent`) or by disabling this market for a time interval (`DisableIntervalMarketEvent`). 

`EnableMarketEvent` / `DisableMarketEvent` commands each accept one argument, which is the hour at which this event is triggered (hourly resolution is supported in the current implementation), and this area will be enabled/disabled at this specific point in time no matter its current state. `DisableIntervalMarketEvent` accepts two arguments, denoting the **start hour** and the **end hour** at which the Market is disabled.

The term _disabled market_ means that the relevant markets and submarkets are not performing any trading, and are hence inactive in the simulation for the time that the market is disabled. Once enabled, the relevant market and its submarkets will start to operate. 

Examples for these events are available on the Grid Singularity GitHub:

*   EnableMarketEvent: [isolated_enable_event.py](https://github.com/gridsingularity/d3a/blob/master/src/d3a/setup/area_events/isolated_enable_event.py)
*   DisableMarketEvent: [isolated_disable_event.py](https://github.com/gridsingularity/d3a/blob/master/src/d3a/setup/area_events/isolated_disable_event.py)
*   DisableIntervalMarketEvent: [disable_interval_event.py](https://github.com/gridsingularity/d3a/blob/master/src/d3a/setup/area_events/disable_interval_event.py)

###Connect/Disconnect Market Events

These events are similar to the enable/disable event; both have a similar API and both are used for removing a market from the grid. The difference is that the Connect/Disconnect events are decoupling the relevant submarkets and assets from the main grid. When the event is enabled, there will be two independent grids trading energy internally, but not with each other. This is contrary to enable/disable events, where the subtree is not performing any trades. This can simulate grids that are abruptly decoupled from the main grid, but manage to self-sustain their assets by continuing to trade energy even after they are disconnected from the main grid.

You can find examples for these events on Grid Singularity GitHub:

*   ConnectMarketEvent: [isolated_connect_event.py](https://github.com/gridsingularity/d3a/blob/master/src/d3a/setup/area_events/isolated_connect_event.py)
*   DisconnectMarketEvent: [isolated_disconnect_event.py](https://github.com/gridsingularity/d3a/blob/master/src/d3a/setup/area_events/isolated_disconnect_event.py)
*   DisconnectIntervalMarketEvent: [disconnect_interval_event.py](https://github.com/gridsingularity/d3a/blob/master/src/d3a/setup/area_events/disconnect_interval_event.py)

###Strategy Events

These events are used to change an asset’s trading strategy during the simulation runtime. These are distinct events with no interval event provided.

*   Load StrategyEvent: [load_event.py](https://github.com/gridsingularity/d3a/blob/master/src/d3a/setup/area_events/load_event.py)
*   PV StrategyEvent: [pv_event.py](https://github.com/gridsingularity/d3a/blob/master/src/d3a/setup/area_events/pv_event.py)
*   Storage StrategyEvent: [storage_event.py](https://github.com/gridsingularity/d3a/blob/master/src/d3a/setup/area_events/storage_event.py)

###Configuration Events

These events are used to change the market configuration (including submarkets and assets) during runtime. A useful application for this event is to set different weather conditions for a subset of the grid. Configuration events are distinct and no interval event is provided. There are currently two configuration events:

*   Cloud Coverage Event: [cloud_coverage_event.py](https://github.com/gridsingularity/d3a/blob/master/src/d3a/setup/area_events/cloud_coverage_event.py)
*   PV User Profile Event : [userprofile_pv_event.py](https://github.com/gridsingularity/d3a/blob/master/src/d3a/setup/area_events/userprofile_pv_event.py)