## Spot Market Slots

The energy spot market is broken into slots, the default is set to 15 minutes of simulation time. For a one day simulation, 96 market slots would occur with the default setting. See [How to launch Simulation via Command Line Interface](launch-sim-via-cli.md) for how to adjust market slot length.

Depending on the market type, bids and asks are either matched within or at the end of each slot. Bids and asks that remain unmatched at the end of a market slot are deleted.

## Market Ticks

Each slot is further incremented into ticks. The default setting for a tick is 15 seconds of simulation time, but is [configurable](launch-sim-via-cli.md). The default 15 minute market slot is made up of 60 15-second ticks. The real-time length of both market slots and ticks is determined by the configurable simulation time scale (e.g. 1 simulation-time hour = 1 real-time minute)

With the API, agents are limited to one update to their bids and asks per tick (60 per market slot).

In a pay-as-bid market, the market is cleared at the end of each tick. An order submitted in a tick could be matched at the end of that tick. If the order is not matched, it is propogated to all adjacent markets by the [Inter-Area Agent](inter-area-agent.md) for the next tick. If it is not matched at the end of that tick, it is further propagated to connected markets in the subsequent ticks following the same logic.

For example, assume a bid is created in market `A` in tick `t1`. If markets `A` and `D` are separated by markets `B` and `C`, market `D` would see an unmatched offer from market `A` in `t4`. If a match is found in market `D`, the orders would simultaneously clear in both markets at the end of  `t4` in a pay-as-bid market. In a pay-as-clear market, offers still propagate to adjacent markets each tick. However, clearing happens at the determined clear frequency (default is 3 times per market slot).
