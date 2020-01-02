The market object collects offers and serves the functionality of accepting and deleting offers as well as dispatching these offer events to its listeners (other areas and their markets). The auction is continuous, meaning that once an offer is posted, it can be accepted  right away, even before the end of the slot market.

Energy producing agents (or “sellers”) post offers in the market with an energy price determined by the devices' strategy.

Consuming agents (or “buyers”) can see the offers available in their local market, filter the affordable offers and then select the cheapest offer among them. The energy rate by which the seller and buyer settle is the price of the offer (pay-as-offer).  Consequently, the trade rate may be different than other trades settled in the same slot. 

An [Inter-Area Agent](inter-area-agent.md) is created and operated by each area. Its job is to forward offers to the connected markets. It does not have any strategy allocated to it. 