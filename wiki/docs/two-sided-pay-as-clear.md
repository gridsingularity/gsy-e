In the two-sided market, buyers are able to place bids in the market, alongside the offers placed by sellers (as seen in the one-sided market).

The Two Sided Pay-As-Clear behaves the same as the [Two Sided Pay-As-Bid](two-sided-pay-as-bid.md) market

The only difference is the offer/bid matching algorithm.
Currently, there is a so-called merit-order-effect mechanism implemented that works like the following:
Bids and offers are aggregated in a specified discrete interval (clearing interval). At the end of that interval, bids are arranged in a descending order, offers in an ascending order and the equilibrium quantity of energy and price is calculated. The clearing point (the amount of energy that is accepted [trade volume] for a specific energy rate [clearing rate]) is determined by point where arranged bid curve for the Consumers drops below the offer curve for the Producers.

![img](img\two-sided-pay-as-clear.png)

All offers that have an energy rate below or equal to the clearing rate are accepted and matched randomly with all bids that have an energy rate higher or equal to the clearing energy. The remaining bids and offers (right of the clearing point in the plot above) are not cleared at this clearing point and stay in the market for later matching. 