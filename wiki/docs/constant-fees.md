The constant grid fee is a market based fee, defined in **€/kWh** and added to each trade that is cleared, as shown in the figure below.

<figure markdown>
  ![alt_text](img/grid-fee-constant-1.png){:text-align:center"}
  <figcaption><b>Figure 4.15</b>: Constant grid fee calculation in the Grid Singularity Exchange.
</figcaption>
</figure>

The rate of a bid or offer changes as that bid or offer is propagated into different markets. The offer rate increases to account for the added fees for the relevant market, ensuring that the seller receives a revenue equal or greater than the original offer. The bid rate decreases for the same reason.

##Example Calculation in One-Sided Pay-as-Offer Market

<figure markdown>
  ![alt_text](img/grid-fee-constant-2.png){:text-align:center"}
  <figcaption><b>Figure 4.16</b>: Constant Grid Fee Example Calculation in One-Sided Pay-as-Offer Market.
</figcaption>
</figure>

In an [One-Sided Pay-as-Offer](one-sided-pay-as-offer.md) market, there are no bids, only offers. Offers are propagated throughout the markets in the hierarchy shown in the figure above. Grid fees are accounted for when an offer is forwarded to the higher market, adding that market’s grid fees to any previously accumulated fees. The formula to calculate the new offer rate when placing an offer to a higher market is the following:

```
offer_rate_after_fees (€/kWh) = offer_rate (€/kWh) + grid_fee (€/kWh)
```

If the offer is not purchased after two [ticks](market-types.md#market-ticks), it is moved into the next market, with the total rate incremented by the amount of that market's grid fee. In the example above, the PV offer of 0.10 €/kWh is first placed into the House 2 Market where it gains zero fees. Then it moves into the Neighborhood 2 Market, gaining a fee of 0.01 €/kWh to become 0.11 €/kWh. Then, if not purchased, it moves into the Grid Market, gaining a fee of 0.02 €/kWh to become 0.13 €/kWh. Continuing into the Neighborhood 1 Market, the offer gains a fee of 0.01 €/kWh to become 0.14 €/kWh. Continuing into the House 1 Market, the offer gains zero fees. The Load ultimately buys the offer in the House 1 Market at the Clearing Rate of 0.14 €/kWh.

The trade price is calculated by adding the original offer rate (`0.10 €/kWh`) and the total fees (`(0.01+0.02+0.01) = 0.04 €/kWh`), then multiplying by the amount of energy traded (`1 kWh`) to yield the Trade Price of 0.14€.

The Load pays the Trade Price of 0.14€, which includes 0.10€ revenue for the PV, 0.01€ fees for the Neighborhood Market 1, 0.02€ fees for the Grid Market, and 0.01€ fees for the Neighborhood Market 2.

Since the market type is pay-as-offer, the offer rate is used as the clearing rate. The grid fees are added to the offer rate to determine the trade rate and therefore the trade price in each market. The following formula is used:

```
supply_side_fee (€/kWh) = forwarded_offer_rate (€/kWh) - original_offer_rate (€/kWh)
trade_rate (€/kWh) = clearing rate (€/kWh)
trade_price (€) = energy (kWh) * trade_rate (€/kWh)
```

For the provided example, the trade price for each market is:

```
Market_trade_price (€) = (original_offer_rate (€/kWh) + supply_side_fee (€/kWh)) * energy (kWh)

Grid Market = (0.10 + 0.03)*1 = 0.13
Neighborhood 2 Market = (0.10 + 0.01)*1 = 0.11
Neighborhood 1 Market = (0.10 + 0.04)*1 = 0.14
House 1 Market = (0.10 + 0.04)*1 = 0.14
House 2 Market = (0.10 + 0)*1 = 0.10
```

##Example Calculation in Two-Sided Pay-as-Bid Market

<figure markdown>
  ![alt_text](img/grid-fee-constant-3.png){:text-align:center"}
  <figcaption><b>Figure 4.17</b>: Constant Grid Fee Example Calculation in Two-Sided Pay-as-Bid Market.
</figcaption>
</figure>

In the [Two-Sided Pay-as-Bid](two-sided-pay-as-bid.md) market, there are both bids and offers, and both are propagated through the markets in the hierarchy. If a bid or offer is not matched after two [ticks](markets.md#market-ticks), it is moved into the next market. In order to prevent the double accounting of a market's grid fee when a bid and an offer are matched in that market, market fees are added to offers when they enter a new market (target market), and they are subtracted from bids when they leave a market (source market) and enter another one. The formula for propagating the offers is the same as for the one-sided market :

```
offer_rate_after_fees (€/kWh) = offer_rate (€/kWh) + grid_fee (€/kWh)
```

The IAA subtracts the fees from the bid before propagating the bid to the higher market, based on the following formula:

```
bid_rate_after_fees (€/kWh) = bid_rate (€/kWh) - grid_fee (€/kWh)
```

In the case of a Two-Sided Pay-as-Bid market, the offer is moved into the Grid Market by the same mechanism as in the One-Sided Pay-as-Offer market. The bid of 0.30 €/kWh is placed into the House 1 Market where there are zero fees. If it is not purchased after two ticks, it is moved into the Neighborhood 1 Market. As explained above, only the fees from the source market are added, which are zero in this case. Hence the bid rate remains 0.30 €/kWh. Next, the bid is moved into the Grid Market, where its value is reduced by the amount of the fees of its source market, the Neighborhood 1 Market at 0.01 €/kWh, resulting in a rate of 0.29 €/kWh as it enters the Grid Market.

In the example above, the bid and offer are matched in the Grid Market. When the offer entered the Grid Market, its rate was immediately updated to account for the Grid Market fees (0.11 + 0.02). The bid was not updated, and if it  was not matched in the Grid Market and moved to the Neighborhood 2 Market, the 0.02 €/kWh fee from the Grid Market would be subtracted to become (0.29 - 0.02) 0.27 €/kWh. The fees from the Neighborhood 2 Market would not be added to the bid unless it entered the House 2 Market (fees added according to the source market).

In the Grid Market, the Load bid rate is listed as 0.29 €/kWh and the PV offer as 0.13 €/kWh. As the bid’s rate is greater than the offer’s rate, a trade can be scheduled. The trade clears at the bid’s rate, resulting in a Clearing Rate of 0.29 €/kWh.

The Grid Singularity energy exchange engine includes an algorithm that calculates the grid fee according to the clearing rate, basing the calculation on the original bid and offer rates. This allows the markets to act more independently and in a decentralized manner, without having to share information regarding their fees with other markets. The algorithm formula is as follows:

```
demand_side_fee (€/kWh) = original_bid_rate (€/kWh) - forwarded_bid_rate (€/kWh)
supply_side_fee (€/kWh) = forwarded_offer_rate (€/kWh) - original_offer_rate (€/kWh)
```

For the example, we have the following values:

```
supply_side_fee = 0.13 - 0.10 = 0.03 €/kWh
demand_side_fee = 0.30 - 0.29 = 0.01 €/kWh
```

After calculating the supply and demand side fee, the trade revenue can be calculated. Note the original_trade_rate is the amount that the original buyer (in our case the Load) will need to pay, therefore in the Pay-as-Bid market type this is the original bid price. The formula is the following:

```
total_fee (€/kWh) = supply_side_fee (€/kWh) + demand_side_fee (€/kWh)
revenue_rate (€/kWh) = original_trade_rate (€/kWh) - total_fee (€/kWh)
```

For the example, the revenue will be: revenue = 0.30 - 0.04 = 0.26 €/kWh

Finally, the trade rate is adapted according to the supply side fee, in order to include the fees of the current market:

```
trade_rate (€/kWh) = revenue_rate (€/kWh) + supply_side_fee (€/kWh)
trade_price (€) = energy (kWh) * trade_rate (€/kWh)
```

For our example, the trade price for each market is:

```
Market_trade_price (€) = (revenue_rate (€/kWh) + supply_side_fee (€/kWh)) * energy (kWh)

Grid Market = (0.26 + 0.03)*1 = 0.29,
Neighborhood 2 Market = (0.26 + 0.01)*1 = 0.27,
Neighborhood 1 Market = (0.26 + 0.04)*1 = 0.30,
House 1 Market = (0.26 + 0.04)*1 = 0.30,
House 2 Market = (0.26 + 0)*1 = 0.26.
```

The Load pays the Trade Price of 0.30€, which includes 0.26€ revenue for the PV, 0.01€ fees for Neighborhood Market 1, 0.02€ fees for the Grid Market, and 0.01€ fees for the Neighborhood Market 2.
