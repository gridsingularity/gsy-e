###Configuration Model
![img](img/grid-fee-1.jpg){:style="display: block;margin-left: auto;margin-right: auto;"}
###Introduction and definitions

We will use the grid configuration example above to go into detail about how the grid fees in the D3A work. Grid fees can be configured as percentages or as euro cents (constant fees are not yet implemented). Please see how to configure the grid fee [here](configure-transfer-fee.md). Fees are configured based on the clearing price of the trade. 

We have agreed that the buyer should pay all of the fees, at least for this implementation. Any fee that a seller has to pay is ultimately the burden of the buyer. A seller with additional operational costs or taxes will have to raise their prices in a competitive market.

The fees are typically configured as percentages or euro cents in order to map the D3A fees in a way similar to the energy fees found on a customer's energy bill in the traditional/legacy electricity system. For example, in Germany the federal network agency charges 24% of the total bill as usage fees. Additional fees are subtracted for: Renewable energy surcharge (21%), Sales Tax (16%), Electricity Tax (7%), Concession levy (5%), Offshore liability levy (1.3%), Surcharge for combined heat and power plants (0.1%) and Levy for industry rebate on grid fees (1%). See [Clean Energy Wire](https://www.cleanenergywire.org/factsheets/what-german-households-pay-power) for more info. When running D3A simulations, we consider the current grid fees and propose which fees need to be added at which layers in the D3A. Configuring separate grid fees in separate markets or areas helps to accomplish this. The grid fee is a part of the energy trade price and is cumulative so that the fees in each market a trade passes through can be added cumulatively together to get the entire grid fee, often as a percentage of the clearing price. 

The **Clearing Price** is the price that the market clears at.

The **Trade Price** is the price the buyer pays (revenue to the seller plus the grid fees).

As seen in the examples below, the price of a bid or offer changes as it is propagated into different markets. The price of an offer increases to account for the added fees of the market. This helps an agent submitting an offer to receive equal or greater revenue than the value of the offer. The price of a bid decreases for the same reason. This helps an agent submitting a bid to pay equal or less than the value of the bid. This way, an agent making an offer will never receive less than their offer and an agent making a bid will never pay more than the bid.

###One Sided Pay as Offer
![img](img/grid-fee-2.jpg){:style="display: block;margin-left: auto;margin-right: auto;"}

In the One Sided Pay as Offer market, there are no bids and only offers exist. The offers are propagated throughout the markets in the hierarchy. The grid fees are taken into account when an offer is forwarded to the higher market, by the higher market itself. Therefore the agent is not responsible for adapting the offer price to include the grid fees. The grid fees' unit is a ratio of the original offer price, therefore the formula to calculate the new offer price when placing an offer to a market is the following:

```
offer_price_after_fees = offer_price + original_offer_price * grid_fee_ratio
```
If the offer is not purchased after one tick, it is moved into the next market. When entering a new market, the offer's price is increased according that that market's grid fee. The PV offer of € 0.10 is first placed into the House 2 Market where it gains zero fees. Then it moves into the Neighborhood 2 Market, gaining a fee of 5% of the original offer `0.10*0.05+0.10=0.105` to become € 0.105. Then if not purchased it moves into the Grid Market, gaining a fee of 10% of the original offer `0.10*0.10+0.105=0.115` to become € 0.115. Continuing into the Neighborhood 1 Market, the offer gains a fee of 5% `0.10*0.05+0.115=0.12` to become € 0.12. Continuing into the House 1 Market, the offer gains zero fees. The Load buys the offer in the House 1 Market at the Clearing Price of € 0.12. From the initial offer price, the total fees are calculated `0.10*(1+0.05+0.10+0.05)` to yield the Trade Price of € 0.12.

**The Load pays the Trade Price of € 0.12, which includes € 0.10 revenue to the PV, € 0.005 fees to Neighborhood Market 1, € 0.01 fees to Grid Market, and € 0.005 fees to Neighborhood Market 2.**

Since the market is pay-as-offer, the offer prices are used as 'clearing' prices. On each market trade, the grid fee is calculated based on the original offer price (according to the accepted energy to cover partial trades) and subtracted from the offer price, in order to calculate the trade price after fees. However, the trade price includes the grid fees. The following formula is used: 
```
market_fees = grid_fee_ratio * original_price * energy_portion
trade_price_after_fees = energy * trade_rate - market_fees
trade_price = energy * trade_rate
```

###Two Sided Pay as Bid
![img](img/grid-fee-3.jpg){:style="display: block;margin-left: auto;margin-right: auto;"}

In the Two Sided Pay as Bid market, there are both bids and offers, which are both propagated throughout the markets in the hierarchy. If a bid or offer is not purchased after one tick, it is moved into the next market. In order to prevent the double accounting of a market's grid fee when a bid and an offer are matched in that market, market fees are added to offers when they enter that market (**target market**) and market fees are subtracted from bids when they leave that market and enter the another one (**source market**). The formula for propagating the offers is exactly the same as on the one-sided market :
```
offer_price_after_fees = offer_price + original_offer_price * grid_fee_ratio
```
The bids are not adapted by the market itself, but the area/IAA is responsible to subtract the fees from the bid before propagating the bid to the higher market. As mentioned above, the difference in behavior compared to offers is to avoid double accounting of the grid fee on one market. The formula for an area to update the bid to include grid fees is the following:
```
bid_price_after_fees = bid_price - original_bid_price * grid_fee_ratio
```
In the case of the Two Sided Pay as Bid market, the offer has moved into the Grid Market by the same mechanism as explained in the One Sided Pay as Offer market. The bid of € 0.30 follows a similar mechanism and is placed into the House 1 Market where there are zero fees. If the bid is not purchased after one tick, it is moved into the Neighborhood 1 Market. As explained above, only the fees from the source market are added, which are zero in this case. So the bid remains at € 0.30. Next the bid moves into the Grid Market, where it its value is lowered according to the fees of its source market, the Neighborhood 1 Market at 5%. With the Neighborhood 1 Market fee, the bid is lowered to `0.30-0.30*0.05=0.285` € 0.285 as it enters the Grid Market.

In the example above, the bid and offer are matched in the Grid Market. However, when the offer entered the Grid Market, its price was immediately updated to account for the Grid Market's fees `0.10*0.10+0.105=0.115`. The bid on the other hand did not add the 10% fee. In the case that the bid was not matched in the Grid Market and moved into the Neighborhood 2 Market, the 10% fee from the Grid Market would be added. In this case the bid would become `0.285-0.30*0.10=0.255` € 0.255. The fees from the Neighborhood 2 Market would not be added to the bid unless it entered the House 2 Market (fees added according to the source market).

In the Grid Market, the Load bid is listed as € 0.285 and the PV offer is listed as € 0.115. As the bid is greater than the offer a trade can be scheduled. The trade clears at the bid price, giving a Clearing Price of € 0.285.

There is a separate algorithm that calculates the grid fee according to the clearing price. This allows the markets to act more independently and in a decentralized manner, without having to share information regarding their fees with other markets. In order to calculate the fee correctly based on the original price, the algorithm needs to be able to calculate the supply side and demand side tax. It is easy to calculate this, since the original bid/offer prices are available:
```
demand_side_tax = 1 - (forwarded_bid_rate / original_bid_rate)
supply_side_tax = (forwarded_offer_rate / original_offer_rate) - 1
```

For the example, we have the following values: `supply_side_tax=(0.115/0.1)-1=0.15`, `demand_side_tax=1-(0.285/0.3)=0.05`.

After calculating the supply and demand side tax, we can calculate the revenue of the trade. Note the original_trade_rate is the amount that the original buyer (in our case the Load) will need to pay, therefore for pay as bid this is the original bid price. The calculation is the following: 
```
total_tax_ratio = supply_side_tax + demand_side_tax
revenue = original_trade_rate / (1 + total_tax_ratio)
```

For the example, the revenue will be: `revenue = 0.30/(1+0.15+0.05)=0.25`

The grid fees are then calculated based on the revenue and the individual market fees.
```
fees = revenue * grid_fee_ratio
```
For the case of the Grid Market in our example, the fees are `0.25*0.1=0.025`, and for each Neighborhood market, the fees are `0.25*0.05=0.0125`. 

Finally, the trade rate is adapted according to the supply side tax, in order to include the fees of the current market: 
```
trade_rate = revenue * (1 + supply_side_tax)
trade_price = energy * trade_rate
```
For our example, the trade price for each market is: 
```
Grid Market = 0.25 * (1 + 0.15) = 0.2875
Neighborhood 2 Market = 0.25 * (1 + 0.05) = 0.2625 
Neighborhood 1 Market = 0.25 * (1 + 0.2) = 0.3
House 1 Market = 0.25 * (1 + 0.2) = 0.3
House 2 Market = 0.25 * (1 + 0) = 0.25
```
**The Load pays the Trade Price of € 0.30, which includes € 0.25 revenue to the PV, € 0.0125 fees to Neighborhood Market 1, € 0.025 fees to Grid Market, and € 0.0125 fees to Neighborhood Market 2.**


###Two Sided Pay as Clear

![img](img/grid-fee-4.jpg){:style="display: block;margin-left: auto;margin-right: auto;"}


The Two Sided Pay as Clear market operates the same as the Two Sided Pay as Bid market, except that an algorithm is used to determine the clearing price, which is uniform for all the trades happening in a particular market. In the Grid Market the bid of € 0.286 is matched with the offer of € 0.115, and the Clearing Price is determined by algorithm as € 0.20. The grid fees are calculated based on the Clearing Price to yield `0.20*(1+0.05+0.10+0.05)=0.24` a Trade Price of € 0.24.

**The Load pays the Trade Price of € 0.24, which includes € 0.20 revenue to the PV, € 0.01 fees to Neighborhood Market 1, € 0.02 fees to Grid Market, and € 0.01 fees to Neighborhood Market 2.**











