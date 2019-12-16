The ESS can buy or sell energy. 

For all cases the initial parameters of the battery can be defined:

- `initial_soc`: Initial battery SOC (State of Charge) in %.
- `min_allowed_soc:` It is the minimum SOC level in % below which the storage bank is never drawn
- `battery_capacity_kWh`: size of the battery (default value: 1.2 kWh)
- `max_abs_battery_power_kW`: maximum power rating for battery charge/discharge, (default value: 5 kW)

Rate settings:

- `update_interval`: time after which the rate should be updated (type: pendulum duration object)
- `initial_selling_rate`: The maximum starting point of offer rate (ct/kWh)
- `final_selling_rate`: The minimum ending point of offer rate (ct/kWh)
- `initial_buying_rate`: The minimum starting point of bid rate (ct/kWh)
- `final_buying_rate`: The maximum ending point of bid rate (ct/kWh)
- `energy_rate_decrease_per_update`: configured as the cents/kWh decrease per update (default value: 1 cent/kWh per update).
- `fit_to_limit:` derive bidding behaviour from a linear fitted curve of a buying rate between `initial_buying_rate` and `final_buying_rate` (boolean value) within the bidding interval. If activated, `energy_rate_increase_per_update = (final_buying_rate - initial_buying_rate) / (market_interval_length / update_interval)`.
- `cap_price_strategy`: the ESS can trade energy based on a capacity dependent sell price (Default: `False`, set to `True` to activate). See Addendum on this page for more information.

In order to enable ESS to participate in balancing market, a prerequisite is to add the ESS device in "[Device Registry](https://gridsingularity.atlassian.net/wiki/spaces/D3A/pages/23887933/Markets+-+balancing+market)" and set the following parameters:

- `balancing_energy_ratio`: the first value dictates the ratio of energy to be charged from balancing market. The second value dictates the ratio of energy to be discharge to balancing market (default value: tuple(0.1, 0.1))

Corresponding code: `src/3a/models/strategy/storage.py`

How to add a Storage device to the setup-file:

```
Area('Storage', strategy=StorageStrategy(initial_soc=50,
                                         energy_rate_decrease_per_update=3,
                                         battery_capacity_kWh=1.2,
                                         max_abs_battery_power_kW=5,
                                         final_buying_rate=16.99,
                                         final_selling_rate= 17.01)),
               appliance=SwitchableAppliance()),
```

------

#### Addendum: ESS Capacity Based Method

This method was created to sell energy at lower prices during high SOC (when the battery has more energy stored) and at higher prices during low SOC (when the battery can afford to sell its stores less).

If the cap_price_strategy is true, the offer price for the ESS is calculated according to:

`offer_rate = initial_selling_rate - ((initial_selling_rate - final_selling_rate)\*soc/100)`

As an example, considering an `initial_selling_rate` of 30 cents/kWh and a `final_selling_rate` price of 20 cents/kWh, an ESS with an SOC of 1% would sell its energy at 29.9 cents/kWh, and a battery at 100% SOC would sell its energy at 20 cents/kWh.



## General Behaviour

In general all offers and bids follow the physical constraint of the set `max_abs_battery_power_kW` Value. The accumulated energy per market slot can not exceed this power value. Here selling and buying cancel each other out meaning that if 2kWh are both sold and bought in the same market slot, the relative power is still 0.

For the buying rate increase and selling rate decrease behaviour, please see: [How the Strategies Adjust the Prices of Offers and Bids](how-strategies-adjust-prices.md). 

### Buying Energy

#### One Sided Market

On every tick, the storage scans the connected market for affordable offers\* if there is storage space to be filled (if the current SOC is lower than 100%). Once an offer is found, it is either fully or partially accepted, depending on the demand. The storage always seeks for 100% SOC when buying energy.

 \* = affordable offers are offers that have a price lower or equal the current acceptable energy rate. The acceptable energy rate changes in the frame of one market slot depending on the `initial_buying_rate`, `final_buying_rate`, `energy_rate_decrease_per_update` and `update_interval setting`.

#### Two Sided Market

On every tick, the storage either places a bid for the energy portion it needs to reach 100% SOC or updates the price of an existing bid in the market where the bid price is depending on the `initial_buying_rate`, `final_buying_rate`, `energy_rate_decrease_per_update` and `update_interval setting`.

### Selling Energy

At the beginning of each slot market, the storage places an offer on the market offering all the energy it has stored (not including the energy that is needed to keep the storage at least at `min_allowed_soc`). This offer gets updated on every tick following the rate decrease settings. 
This applies to both one and two sided market types. 
Consequently, it is possible for the storage to have both an offer and a bid placed in the same market. 