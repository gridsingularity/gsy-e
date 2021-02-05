![alt_text](images/image1.png "image_tooltip")

Structure of Balancing Market in Grid Singularity energy exchange (D3A)

Grid Singularity energy exchange (D3A) bottom-up market design allows participants to engage in Local Energy Market (LEM) for energy trading, providing energy balance at a local level. D3A flexibility trading also facilitates the procurement of flexibility locally from participants to assist distribution grid operation in balancing the grid.

##Assets

In the Grid Singularity D3A, balancing has been implemented using:

*   Fast responding non-critical loads to provide load shedding
*   Battery storage
*   Commercial power plants

The trading strategies of energy assets like [Loads](model-load.md), [Storages](model-storage.md) and [Power Plants](model-power-plant.md) can be used to balance the grid by placing balancing offers. These assets participate in the balancing market only if they are registered in the [Asset Registry](balancing-implementation.md#asset-registry).

##Asset Registry

How to register an energy asset in the registry in the the setup file:

The balancing asset registry is a dictionary that contains the names of assets as keys and the balancing rates as tuple values: (demand balancing rate, supply balancing rate).

```
asset_registry_dict = {
    "H1 General Load": (33, 35),
    "H2 General Load": (33, 35),
    "H1 Storage1": (33, 35),
    "H1 Storage2": (33, 35),
}
```

###Balancing Market

The present setting is a [One-Sided Pay-as-Offer market](one-sided-pay-as-offer.md), which accepts _balancing_offers_ from energy assets and connected hierarchies of _balancing_market_. _balancing_offers_ could be positive or negative. It also facilitates the _balancing_trade_.

###Balancing Agent

The balancing agent follows the lead of the _spot_market_trade_ of its lower hierarchy. Whenever there is a trade in the lower hierarchy of _spot_market_, it will try to secure a share of spot market trades in the balancing market.

###Constant Parameters

The following are the constant parameters related to the balancing market and are declared [here](https://github.com/gridsingularity/d3a-interface/blob/master/d3a_interface/constants_limits.py#L176-L189).

ENABLE_BALANCING_MARKET →  (Default: False) (It enables the simulation with Balancing Market)

BALANCING_SPOT_TRADE_RATIO →  (Default: 0.2) (It dictates the ratio of _spot_market_energy_ to be traded in balancing market)

BALANCING_OFFER_DEMAND_RATIO → (Default: 0.1) (It dictates the ratio of _spot_market_energy_ to be offered in balancing market as _demand_balancing_offer_)

BALANCING_OFFER_SUPPLY_RATIO → (Default: 0.1) (It dictates the ratio of _spot_market_energy_ to be offered in balancing market as _supply_balancing_offer_)

BALANCING_FLEXIBLE_LOADS_SUPPORT → (Default: True) (It enables [Load Strategy](model-load.md) to place _supply_balancing_offer_ (effectively curtailing it's load))

Multiple examples of balancing market setup are available [here](https://github.com/gridsingularity/d3a/tree/master/src/d3a/setup/balancing_market).