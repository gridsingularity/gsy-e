Simulation events are changes in the configuration/setup that take place during normal execution of a simulation. They have to be defined by the user in the setup files before the start of the simulation, and they are associated with a specific point in time (or duration), at which point the event is triggered. An event has to be associated with an area, thus there is a new constructor parameter on the area, namely '`event_list`', that accepts a list of events for this specific area.

There are 4 different event types: 

- Add/Remove area event 
- Connect/Disconnect area event
- Strategy events
- Config events

Each is described in detail below.

### Add/Remove area event

This event is associated with an area, and dictates that this area (and its children) will be added or removed from the grid at a specific point in time. There are 2 ways to configure this behaviour, either via individual events (`EnableAreaEvent` and `DisableAreaEvent`) or to configure this area to be disabled for a time interval (`DisableIntervalAreaEvent`). `EnableAreaEvent` / `DisableAreaEvent` accept only one argument, which is the hour that this event is triggered (hourly resolution is supported in events for now, minute resolution is under consideration if we see the need for it), and this area will be enabled/disabled at this specific point in time no matter its current state. `DisableIntervalAreaEvent` on the other hand, accepts 2 arguments, which denote the start hour and the end hour that the area is disabled. 

The term 'disabled area' means that the area and all the areas under it are not performing any trading, meaning that the entire sub-tree based on this area is taken off the simulation for the time that the area is disabled. Once the area is enabled, the sub-tree will continue to operate. It is designed this way in order to simulate areas being added or removed from the grid, since it is easier to configure and much more optimal for the UI and D3A to have one configuration scenario with parts of it being disabled at certain points in time, instead of creating new areas during the simulation.

You can find examples for these events on github: 

- `EnableAreaEvent`: [isolated_enable_event.py](https://github.com/gridsingularity/d3a/blob/master/src/d3a/setup/area_events/isolated_enable_event.py)
- `DisableAreaEvent`: [isolated_disable_event.py](https://github.com/gridsingularity/d3a/blob/master/src/d3a/setup/area_events/isolated_disable_event.py)
- `DisableIntervalAreaEvent`: [disable_interval_event.py](https://github.com/gridsingularity/d3a/blob/master/src/d3a/setup/area_events/disable_interval_event.py)

### Connect/Disconnect area event

These events are similar to the enable/disable event, both event types have a similar API and both are used for removing an area from the grid. The difference between the 2 is that the Connect/Disconnect events are decoupling their children from the main grid, meaning that during the time that the event is enabled, there are going to be 2 independent grids both trading energy internally, but not trading energy to each other. This is contrary to enable/disable event, where the sub-tree is not performing any trades at all. This is useful to showcase examples from grids that are abruptly decoupled from the main grid, but manage to self-sustain their devices by continuing to trade energy even after they are disconnected from the main grid. 

You can find examples for these events on github: 

- `ConnectAreaEvent`: [isolated_connect_event.py](https://github.com/gridsingularity/d3a/blob/master/src/d3a/setup/area_events/isolated_connect_event.py)
- `DisconnectAreaEvent`: [isolated_disconnect_event.py](https://github.com/gridsingularity/d3a/blob/master/src/d3a/setup/area_events/isolated_disconnect_event.py)
- `DisconnectIntervalAreaEvent`: [disconnect_interval_event.py](https://github.com/gridsingularity/d3a/blob/master/src/d3a/setup/area_events/disconnect_interval_event.py)

### Strategy events

These events are used to change the parameters of the strategy of an area during the simulation runtime. They are applicable for all types of strategies (Load, Storage and PV) and are able to modify different parameters according to the target strategy. These are distinct events and no interval event is provided for strategy events. 

- `Load StrategyEvent`: [load_event.py](https://github.com/gridsingularity/d3a/blob/master/src/d3a/setup/area_events/load_event.py)
- `PV StrategyEvent`: [pv_event.py](https://github.com/gridsingularity/d3a/blob/master/src/d3a/setup/area_events/pv_event.py)
- `Storage StrategyEvent`: [storage_event.py](https://github.com/gridsingularity/d3a/blob/master/src/d3a/setup/area_events/storage_event.py)

### Config events

These events are used to change the config of an area during runtime. This event is also applied to all children of this area, meaning that if a config parameter is changed on one area, the same config parameter will be changed for its children, but not for its parents. A useful application for this is to be able to set different weather conditions for a subset of the grid. The config parameters that are available as events are cloud coverage and the PV user profile (for now, if there is a need to modify other config parameters during the simulation these will be added). Furthermore, config events are distinct and no interval event is provided. 

- `Cloud Coverage Event`: [cloud_coverage_event.py](https://github.com/gridsingularity/d3a/blob/master/src/d3a/setup/area_events/cloud_coverage_event.py)