The Market Maker Strategy mimics the behaviour of a typical energy utility and is used as a reference point. It can work in following modes:

- `grid_connected`: In this mode, it has the ability to meet the infinite energy demands of consumers at the most expensive 'energy_rate' that could exist in that grid.
- `islanded`: In this mode, it won’t fulfill the energy demands of any consumer but would only be used as a reference point of the highest possible `energy_rate` that could exist in that grid.

Following are the parameters needed for its configuration:

- `energy_rate`: It could be a float value OR a time-series value that gives the ability to have different value for every `market_slot`.
- `grid_connected`: If set to `True`, enables it to work in `grid_connected'`mode as explained above. OTHERWISE, it would operate in `islanded` mode.

 

Corresponding code: `src/d3a/setup/strategy_tests/market_maker_strategy.py`

How to add Market Maker to the setup-file:

```
Area('Market Maker', strategy=MarketMakerStrategy(energy_rate=35,
                                                  grid_connected=True),
     appliance=SimpleAppliance()),
```