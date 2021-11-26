Prosumer assets can post orders (bids/offers) of their energy deviations to the settlement market in order to get compensated by another entity that deviated in the opposite direction. Energy deviations are calculated from the difference between the forecasted and measured production or consumption.

##External asset strategies

Aggregator users can post the forecasted and measured energy to the Grid Singularity exchange for each market slot via the Asset API with the batch commands _set_energy_forecast_ and _set_energy_measurement_.

Posting and updating bids and offers works the same as in the spot markets. If the provided _time_slot_ is a settlement market already the order is placed or updated in the settlement market. The external client can only post maximally the amount of energy of the deviation to the settlement market.

![alt_text](img/assets-strategies-1.png)

**Figure 3.10**. *Settlement market posting energy deviations mechanism with external asset strategies.*

##Template asset strategies

For the template strategies, the forecasted energy is provided by the user, either by uploading a profile or setting up a predefined PV or Load. The forecasted energy is used to post bids or offers to the spot markets.

The actual measured energy is calculated by a random deviation of the forecasted value. A gaussian random error is simulated (positive and negative deviances around the forecasted energy value possible). The intensity of this random deviation can be controlled by the following setting that represents the relative standard deviation, so the width of the random deviation around the energy forecast:

[`ConstSettings.SettlementMarketSettings.RELATIVE_STD_FROM_FORECAST_FLOAT`](https://github.com/gridsingularity/gsy-framework/blob/175a9c3c3295b78e3b5d7610e221b6f2ea72f6ec/gsy_framework/constants_limits.py#L71).

The template strategies will post orders (bids / offers) with energy values equal to the energy deviations for each market. For example, if a PV forecasted to produce 5kWh of energy for the 12:00 market, but the simulated measured energy reveals that it only produced 4kWh for that time slot, the template strategy will post a bid to the 12:00 settlement market with the energy 1kWh. The behavior for the price increase of this bid is the same as in the spot market: the energy rate of the bid is increased during the market until the final selling rate is reached.

As the settlement market will stay available for longer than the normal spot market (configurable by [`Const.Settings.SettlementMarketSettings.MAX_AGE_SETTLEMENT_MARKET_HOURS`](https://github.com/gridsingularity/gsy-framework/blob/175a9c3c3295b78e3b5d7610e221b6f2ea72f6ec/gsy_framework/constants_limits.py#L69), please also see here), the template strategy will not update the orders as frequent as in the normal spot market, but in the interval that can be set by the parameter [`SettlementTemplateStrategiesConstants.UPDATE_INTERVAL_MIN`](https://github.com/gridsingularity/gsy-e/blob/7f5d2866cfd8b8327e590a1377db2d9bd2909746/src/gsy_e/constants.py#L72).

![alt_text](img/assets-strategies-2.png)

**Figure 3.11**. *Settlement market posting energy deviations mechanism with template asset strategies.*
