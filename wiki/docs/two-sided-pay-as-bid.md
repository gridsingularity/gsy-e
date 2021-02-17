In the Two-Sided Pay-as-Bid market, buyers are able to place bids in the market, alongside the offers placed by sellers.

Each market collects and matches bids and offers issued by trading agents, and dispatches bids and offers to other markets via the [Inter-Area Agent](inter-area-agent.md) (IAA). Bids and offers can also be annulled by the trading agent.

The auction is **continuous**, meaning that once an offer or bid is posted, it can be matched right away, even before the end of the market slot.

An Inter-Area Agent is created and operated by each [market (area)](model-markets.md). Its role is to forward offers and bids to the connected markets. The market constantly triggers the matching between bids and offers according to the matching algorithm as illustrated in the figure below.

![alt_text](img/pay-as-bid-1.png)

