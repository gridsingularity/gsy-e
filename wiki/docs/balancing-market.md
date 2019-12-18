## Device Registry

Any device first has to get registered before actually placing offers in balancing market.

**HOW TO REGISTER A DEVICE IN THE REGISTRY IN THE SETUP FILE:**

The balancing device registry is a dictionary that contains the names of the devices as keys and the balancing rates as the tuple values: (demand balancing rate, supply balancing rate). 

```
device_registry_dict = {
    "H1 General Load": (33, 35),
    "H2 General Load": (33, 35),
    "H1 Storage1": (33, 35),
    "H1 Storage2": (33, 35),
}
```



## Devices

Currently, [Load Strategy](load-strategy.md) / [Storage Strategy](ess-strategy.md) / [Infinite Power Plant (Commercial Producer)](infinite-power-plant-strategy.md) can place balancing offers only if they are registered in "Device Registry".

## Balancing Market

It is a single sided Pay-as-Ask market, accepts `balancing_offers` from devices and connected hierarchies of `balancing_market`. `balancing_offers` could be positive or negative. It also facilitates the `balancing_trade`.

## Balancing Agent

It listens to the `spot_market_trade` of its lower hierarchy. Whenever there is a trade in lower hierarchy of `spot_market`, it will to try secure a percentage of spot market trades in balancing market.



## Constant Parameters

Following are the constant parameters related to balancing market

`ENABLE_BALANCING_MARKET → (Default: False)` : enables the simulation with Balancing Market
`BALANCING_SPOT_TRADE_RATIO → (Default: 0.2)` : dictates the ratio of `spot_market_energy` to be traded in balancing market
`BALANCING_OFFER_DEMAND_RATIO → (Default: 0.1)` : dictates the ratio of `spot_market_energy` to be offered in balancing market as `demand_balancing_offer`
`BALANCING_OFFER_SUPPLY_RATIO → (Default: 0.1)` : dictates the ratio of `spot_market_energy` to be offered in balancing market as `supply_balancing_offer`
`BALANCING_FLEXIBLE_LOADS_SUPPORT → (Default: True)` : It enables [Load Strategy](load-strategy.md) to place `supply_balancing_offer` (effectively curtailing it's load)