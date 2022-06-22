Batteries (also known as energy storage) are energy assets that save the surplus energy produced and store it for use at a later time. Adding a battery to a home or community will increase the self-consumption and self-sufficiency levels and enhance the potential of flexibility service for grid operators.

##Asset Configuration Options

**Express Mode**

1. Name - Must be unique
2. Geo-tag - This automatically uploads the location a user selects

**Advanced Mode**

1. Battery capacity - Users can choose the total energy capacity in kWh.
2. Initial capacity - Set the initial capacity of the battery in terms of Initial State of Charge (SOC) in %, or Initial Energy in kWh. This will set the initial level of charge of the battery at the start of the simulation.
3. Minimum SOC - Choose the minimum amount of energy to leave in the battery. Batteries usually have a safeguard disabling them to discharge below a specific threshold to increase life expectancy.
4. Max power rating for battery - Choose the power limit (charge and discharge) for each market slot in kW. This parameter limits the maximum sold and bought energy.
5. Initial selling rate - Users can choose the initial  rate for selling energy at the beginning of each market slot in cents/kWh.
6. Final selling rate - Users can choose the final rate for selling energy at the end of each market slot in cents/kWh.
7. Rate decrease - Users can choose the explicit rate decrease increment in cents/kWh.
8. Initial buying rate - Users can choose the initial rate for buying energy at the beginning of each market slot in cents/kWh.
9. Final buying rate - Users can choose the final rate for buying energy at the end of each market slot in cents/kWh.
10. Rate increase - Users can choose the explicit rate increase increment in cents/kWh.
11. Fit to Limits - If activated, a rate decrease per time is calculated, starting at initial Selling Rate and ending at final Selling Rate while updating the rate at each Update Interval Bidding behaviour is derived from a linear fitted curve of a buying rate between initial_buying_rate and final_buying_rate and a selling rate between initial_selling_rate and final_selling_rate within the bidding interval. If activated: energy_rate_increase = (final_buying_rate - initial_buying_rate) / max(int((slot_length / update_interval) -1), 1) energy_rate_decrease_per_update = (initial_selling_rate - final_selling_rate) / max(int((slot_length / update_interval) -1), 1)
12. Update interval - Users can choose the frequency at which the rate is updated.
13. Capacity based method - If activated, energy will be sold at lower prices during high state of charge - SOC (when the battery has more energy stored) and at higher prices during low SOC (when the battery can afford to sell its stored energy for less). If chosen, the offer price for the storage is calculated according to:

```
offer_rate = initial_selling_rate - ((initial_selling_rate - final_selling_rate)\*soc/100)
```

As an example, considering an initial_selling_rate of 30 cents/kWh and a final_selling_rate of 20 cents/kWh, a storage with an SOC of 1% would sell its energy at 29.9 cents/kWh, and a battery at 100% SOC would sell its energy at 20 cents/kWh.

*Note: The current default setting of  the battery component is 100% energy conversion efficiency.  It is not possible to change this setting at the moment but it may be in the future versions of the software. Interested contributors may propose such additions to our open source code on [GitHub](https://github.com/gridsingularity/gsy-e).*

![alt_text](img/battery-advanced.png)

***Figure 2.12***. *Battery (Storage) Advanced Configuration Options*

##Storage Behaviour in Local Energy Markets

In general, all bids and offers follow the physical constraint of the set ```max_abs_battery_power_kW value```. The accumulated energy per market slot cannot exceed this power value times the length of the market slot, in hours. Energy sold and bought cancel each other out, meaning that if 2kWh are both sold and bought in the same market slot, the relative power remains 0kW.

For the buying rate increase and selling rate decrease behaviour, please see the [Trading Strategies page](default-trading-strategy.md).

**Buying energy in the [One-Sided Market](one-sided-pay-as-offer.md)**

On each tick, the storage scans the connected market for affordable offers* if there is storage space to be filled (if the current SOC is lower than 100%). Affordable offers are offers that have a price lower or equal to the current acceptable energy rate. The acceptable energy rate changes during a market slot depending on the initial_buying_rate, final_buying_rate, energy_rate_decrease_per_update and update_interval setting. Once an offer is found, it is either fully or partially accepted, depending on the demand. The storage always seeks 100% SOC when buying energy.

**Buying energy in the [Two-Sided Market](two-sided-pay-as-bid.md)**

On each tick, the storage either places a bid for the quantity of energy it needs to reach 100% SOC or updates the price of an existing bid in the market where the bid rate depends on the initial_buying_rate, final_buying_rate, energy_rate_decrease_per_update and update_interval setting.

**Selling energy**

At the beginning of each market slot, the storage places an offer for all the energy it has stored (not including the energy that is needed to keep the storage at least at min_allowed_soc). This offer is updated at each update_interval pursuant to the rate decrease settings. This mechanism applies in both one and two-sided market types. Consequently, it is possible for the storage to have both an offer and a bid placed in the same market.
