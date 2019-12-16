This device is the same as the commercial energy producer / infinite power plant in that it produces an infinite amount of energy at the `energy_sell_rate`. 
However, the infinite bus can also buy an infinite amount of energy at a predefined price, the `energy_buy_rate.`

Configuration parameters:

- `energy_buy_rate`: energy rate for selling in cents/kWh (can be a profile in JSON or dict format as well as a filename) 
- `energy_sell_rate`: energy rate for buying in cents/kWh (can be a profile in JSON or dict format as well as a filename) 

Corresponding code: `src/3a/models/strategy/infinite_bus.py`

How to add a infinite power plant to the setup-file:

```
Area('Infinite Bus', strategy=InfiniteBusStrategy(energy_buy_rate=24, energy_sell_rate=25),
                             appliance=SimpleAppliance()),
```