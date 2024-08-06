In the Matching API, seven event types are triggered while a simulation is running. To facilitate offer and bid requests and clearing, the client will get notified via events. It is possible to capture these events and react to them by overriding the corresponding methods.

### Each new market slot

```
def on_market_cycle(self, data):
```

The method  on_market_cycle is triggered at the start of every market slot.

### On % of market completion

```
def on_tick(self, data):
```

The method on_tick is called when a new [tick](market-types.md#market-ticks) is started, at each 1-2% of the market slot completion. It performs an HTTP request to get all open bids and offers posted on the exchange. The response can be received in the method named [on_offers_bids_response](matching-api-events.md#on-offers-bids-response).

### On offers bids response

```
def on_offers_bids_response(self, data):
```
The method on_offers_bids_response is triggered when open [offers/bids](trading-agents-and-strategies.md) responses are returned. The **data** dictionary received from the exchange contains information on all open bids/offers posted. The structure is shown below:

```json
{'8f7b7e7b-0f4a-490b-853f-6017af84ef60':
{‘2021-12-20T00:00’:
{'bids': [{'type': 'Bid', 'id': '5934bfff-43c6-4870-8f1f-52bb8374a1f9',
'energy': 0.05,
'energy_rate': 2.5,
'original_price': 0.125,
‘creation_time’: ‘2021-12-20T00.00:25’,
‘time_slot’: ‘2021-12-20T00:00’,
‘attributes’: None,
‘requirements’: None,
'buyer_origin': 'load',
'buyer_origin_id': 'fcbe2390-5bcf-4cbd-b4f4-7c6d44fda34f',
'buyer_id': 'fcbe2390-5bcf-4cbd-b4f4-7c6d44fda34f',
'buyer': 'load'}],
'offers': [{'type': 'Offer', 'id': 'c4b10dd5-eb5f-4807-859a-9b6a0592a21c',
'energy': 1.25,
'energy_rate': 29.64285714288,
'original_price': 37.0535714286,
‘creation_time’: ‘2021-12-20T00.00:25’,
‘time_slot’: ‘2021-12-20T00:00’,
‘attributes’: None,
‘requirements’: None,
'seller': 'IAA House 2',
'seller_origin': 'H1 Storage1',
'seller_origin_id': 'e9faeda1-ce20-4789-b61c-61559a95f9fb',
'seller_id': 'a4403967-3e47-4d47-8c63-b5145d6c1e42'} ]}]}}
```
where '8f7b7e7b-0f4a-490b-853f-6017af84ef60' refers to a unique identifier of both the market slot and the market in which the corresponding bids / offers have been posted.

### On matched recommendations response

```
def on_matched_recommendations_response(self, data):
```
When the matching engine client sends trades recommendations, this function is triggered and a response is passed through the **data** dictionary.

### On area map response

```
def on_area_map_response(self, data):
```

This method is triggered once at the beginning of the simulation and it is used to build the list of market IDs from which the user wants to request bids and offers from through the [request_offers_bids](matching-api-commands.md#requestoffersbids) command.

### On event or response

```
def on_event_or_response(self, data):
```
Each time an event arrives or any response (from sending a batch of recommendations) is triggered, this information is passed through `on_event_or_response`.

### On finish
```
def on_finish(self, data):
```
This executes when the simulation ends and can be used to trigger exporting data, training a model or exiting the code.
