The Grid Singularity API client allows you to create agents that follow custom trading strategies to buy and sell energy in the energy market. The agent can request and receive information through the Asset API, feed that information into an algorithm, and post bids or offers on a live simulated exchange. 

![alt_text](images/image1.jpg "image_tooltip")


##API Commands

###Event-Triggered Functions

In order to facilitate bid and offer management and scheduling, a python file with the class Oracle is provided. The Oracle class acts as an information aggregator for all of the energy assets (e.g. loads and PVs) you manage, and allows you to post bids and offers on their behalf. A few functions are triggered on different types of events, and can be overridden, useful to take actions when market events occur.

####Each new market (`ON_MARKET_CYCLE(SELF, MARKET_INFO)`)

When a new market slot is available the client will get notified via an event. It is possible to capture this event and perform operations after it by overriding the on_market_cycle method.

Ex: def on_market_cycle(self, market_info):

In the variable market_info you will get a dictionary with information on the market and your assets. You receive information for each asset you manage. The return values are the following :

```json
{

  "name": "house2",

  "id": "13023c7d-205d-4b3a-a434-02375eb277ca",

  "start_time": # start-time of the market slot,

  "duration_min": # 15,

  "asset_info": {

    "energy_requirement_kWh": # energy that the asset has to buy during this market slot,

    "available_energy_kWh": # energy that the asset has to sell during this market slot

  },

  "event": "market",

  "asset_bill": {

    "bought": # energy bought in kWh,

    "sold": # energy sold in kWh,

    "spent": # money spent in €,

    "earned": # money earned in €,

    "total_energy": # bought - sold,

    "total_cost": # spent - earned,

    "market_fee": # € that goes in grid fee,

    "type": # type of the strategy

    },

  "last_market_stats": {

    "min_trade_rate": # minimum trade price in €/kWh,

    "max_trade_rate": # maximum trade price in €/kWh,

    "avg_trade_rate": # average trade price in €/kWh,

    "total_traded_energy_kWh": # total energy traded in kWh

    }

}
```

####On % of market slot completion (ON_TICK(SELF, TICK_INFO))

Each 10% of market slot completion (e.g. 10%, 20%, 30%, …), the same information as market_info will be passed, with updated asset energy requirements based on trades. This can be used to update your bid or offer price at these milestones.

####On trade(ON_TRADE(SELF, TRADE_INFO))

Each time the asset you manage completes a trade, information about the trade is passed through trade_info. This information can be stored locally or acted upon.

####On simulation finish (ON_FINISHED(SELF))

This executes when the simulation finishes, and can be used to trigger exporting data, training a model or exiting the code.

###Sending bids and offers

The oracle is able to post bids and offers for multiple assets at the same time. This is implemented already in the template.

A batch_command dictionary structure is used. To update an existing bid with a load and update both your bid and offer with a storage asset, you would use:


```python
batch_commands = {}
batch_commands[asset_event["area_uuid"]] = [
        {"type": "update_bid",
         "price": price,
         "energy": energy},]
batch_commands[asset_event["area_uuid"]] = [
        {"type": "update_bid",
         "price": buy_price,
         "energy": buy_energy},
        {"type": "update_offer",
         "price": sell_price,
         "energy": sell_energy},)
self.batch_command(batch_commands)
```

Note: The total amount of energy bid at any point is limited to the energy requirement of the asset. Updating a bid during a market slot deletes other active bids. Additionally, the price of your bids/offers must be a positive float otherwise it will get rejected by the market.

###Trading Strategies

A simple trading strategy is available in the [template agent](https://github.com/gridsingularity/d3a/blob/master/src/d3a/setup/odyssey_momentum/assets_api_template.py). See the `TODO` flags there to see how you may configure your trading strategy and extract market and asset data.
