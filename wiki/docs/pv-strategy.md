The PV strategy determines the price of the PV offers on the spot market. It also determines what to do when its offer is not immediately accepted by a buyer. Initial parameters that can be defined include:

- `panel_count`: The number of panels in the simulation
- `max_panel_power_W`: Peak power rating per panel
- `update_interval`: time after which the rate should be updated (type: pendulum duration object). Range[1:(slot_length_minute-1)]
- `final_selling_rate`: The minimum offer rate (ct/kWh)
- `initial_selling_rate`: The maximum offer rate (ct/kWh)
- `use_market_maker_rate`: If this flag is set `True`, then agent's `initial_selling_rate` would be overwritten with [Market Maker Strategy](market-maker-strategy.md)'s defined `energy_rate`
- `energy_rate_decrease_per_update`: It is configured as the cents/kWh decrease per update.
- `fit_to_limit`: derive bidding behaviour from a linear fitted curve of a buying rate between `initial_selling_rate` and `final_selling_rate` (boolean value) within the bidding interval. If activated, `energy_rate_decrease_per_update = (initial_selling_rate - final_selling_rate) / max(int((slot_length / update_interval) -1), 1)`.



For information buying rate decrease behaviour, please see: [Energy Rate Settings and Behaviour](how-strategies-adjust-prices.md). 



The PV profile can be configured as a saved profile here (via choosing the *PVPredefinedStrategy*):

- `cloud_coverage`: (0: sunny; 1: partially cloudy; 2: cloudy). Using this parameter, the simulation allows the user to choose between three solar curves that are stored in the simulation for convenience. No default value for this parameter.

![img](img\pv-strategy-1.png)

Corresponding code: `src/d3a/models/strategy/pv.py` or for the predefined PV:`src/d3a/models/strategy/predefined_pv.py`

How to add a PV device to the setup-file:

```
Area('H2 PV', strategy=PVStrategy(panel_count=4, initial_selling_rate=30,
                                  final_selling_rate=5, fit_to_limit=True,
                                  update_interval=duration(minutes=5)),
     appliance=PVAppliance()),
```

In order to understand how the strategy is actually decreasing its `offered_rate` in the case of not getting traded, see the following diagram. 

####  Relation of different parameters for energy pricing

Lets assume the user has configured its *PVStrategy* with these parameters `(initial_selling_rate=30, final_selling_rate=0, fit_to_limit=True, update_interval=5mins)` and `slot_length=15min` At the start of market, PV would place its initial offer at the rate of `initial_selling_rate`. If `fit_to_limit` is set to `True`, it will reduce its `offer_rate` linearly such that its `final_offer` before the end of `market_slot` should be equal to `final_selling_rate`. Number of available updates in such a case is `(slot_length / update_interval) -1) → (15/5 -1)=2`. Therefore, it is possible for a user to update its offer two times inside the same `market_slot`. The first update would happen at 5mins. The calculated `energy_rate_decrease_per_update → (30 - 0) / 2 → 15`. So, the PV will reduce it `selling_rate` at 5th min from 30 to 15 cts/kWh and at 10th min from 15 to 0 cts/kWh.

![img](img\pv-strategy-2.png)