A Matching API template script is available [here](https://github.com/gridsingularity/gsy-matching-engine-sdk/blob/master/gsy_matching_engine_sdk/setups/matching_engine_matcher.py){target=_blank}. See the TODO flags there connect to your preferred customized clearing algorithm and to request, if desired, bids and offers from specific markets.

At the beginning of the Matching API script, the `MatchingEngineMatcher` class is defined as well as the `on_area_map_response` method, which allows the users to define the list of markets from which they want to request bids and offers from.

```python
class MatchingEngineMatcher(base_matcher):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_finished = False
        self.request_area_id_name_map()

    def on_area_map_response(self, data):
        self.id_list = []
        market_list = ["Community"]
        for market in market_list:
            for market_id, name in data["area_mapping"].items():
                if name == market:
                    self.id_list.append(market_id)
```
Right after, the [on_market_cycle](matching-api-events.md#each-new-market-slot) and the [on_tick](matching-api-events.md#on--of-market-completion) methods are triggered. In the latter, the user requests bids / offers from the market.

```python
    def on_market_cycle(self, data):
        pass

    def on_tick(self, data):
        self.request_offers_bids(filters={})
```
In the next section, the bids/offers that had been previously requested from the market are stored in the `matching_data` variable. The matching algorithm ([AttributedMatchingAlgorithm](https://github.com/gridsingularity/gsy-matching-engine-sdk/blob/master/gsy_matching_engine_sdk/matching_algorithms/attributed_matching_algorithm.py){target=_blank} in the example here) takes those data as input and outputs a list of recommendations. Each recommendation is a nested dictionary with the following structure:

```json
[{'market_id': '0fd481d9-98af-43cd-9e98-196c1fe9877f',
  'time_slot': '2021-12-20T00:15',
  'bids': [{'type': 'Bid',
    'id': '6d71f933-0474-4cd8-baa4-97a1f01553c5',
    'energy': 0.05,
    'energy_rate': 22.5,
    'original_price': 1.125,
    'creation_time': '2021-12-20T00:24:00',
    'time_slot': '2021-12-20T00:15:00',
    'attributes': None,
    'requirements': None,
    'buyer_origin': 'H2 General Load1',
    'buyer_origin_id': 'd5133b0b-5c06-4cc8-aaaa-317756659695',
    'buyer_id': 'd5133b0b-5c06-4cc8-aaaa-317756659695',
    'buyer': 'H2 General Load1'}],
  'offers': [{'type': 'Offer',
    'id': '7760bf1d-ddad-47bb-a2ea-7067ea177c07',
    'energy': 9223372036854775807,
    'energy_rate': 22.0,
    'original_price': 2.0291418481080507e+20,
    'creation_time': '2021-12-20T00:15:25',
    'time_slot': '2021-12-20T00:15:00',
    'attributes': None,
    'requirements': None,
    'seller': 'MA House 2',
    'seller_origin': 'Market Maker',
    'seller_origin_id': '4493f3ce-eece-4386-8fc1-e715cf32b85f',
    'seller_id': '0fd481d9-98af-43cd-9e98-196c1fe9877f'}],
  'selected_energy': 0.05,
  'trade_rate': 22.5,
  'matching_requirements': None}]
```

The matching algorithm can be written as a separate class file and can be referenced in the [on_offers_bids_response](matching-api-events.md#on-offers-bids-response) function as:
```python
	recommendations = YourMatchingAlgorithm.get_matches_recommendations(
            matching_data)
```
At the moment, there are 3 default matching algorithms available to use and to build upon:

1. [Pay as Bid algorithm](https://github.com/gridsingularity/gsy-framework/blob/master/gsy_framework/matching_algorithms/pay_as_bid_matching_algorithm.py){target=_blank} - this clears markets continuously during the market slot following this [strategy](market-types.md#two-sided-pay-as-bid-market);
2. [Pay as Clear algorithm](https://github.com/gridsingularity/gsy-framework/blob/master/gsy_framework/matching_algorithms/pay_as_clear_matching_algorithm.py){target=_blank} - this clears markets by ordering bids and offers and defining a single clearing price, following this [strategy](market-types.md#two-sided-pay-as-clear-market);
3. [Attributed matching algorithm](https://github.com/gridsingularity/gsy-matching-engine-sdk/blob/master/gsy_matching_engine_sdk/matching_algorithms/attributed_matching_algorithm.py){target=_blank} - this follows the same logic as the [Pay-as-Bid clearing](https://github.com/gridsingularity/gsy-framework/blob/master/gsy_framework/matching_algorithms/pay_as_bid_matching_algorithm.py){target=_blank} but takes into account [degrees of freedom](degrees-of-freedom.md) such as attributes and requirements (listed as dictionaries for bids and offers):
    - [Attributes](https://github.com/gridsingularity/d3a-api-client/blob/master/README.md#attributes){target=_blank} - “energy type”, currently implemented only for offers (e.g. “green” energy)
    - [Requirements](https://github.com/gridsingularity/d3a-api-client/blob/master/README.md#requirements){target=_blank} - “trading partners” implemented for offers and “energy type”, “trading partners”, “energy”, and “price” implemented for bids.

```python
def on_offers_bids_response(self, data):
        matching_data = data.get("bids_offers")
        if not matching_data:
            return
        recommendations = AttributedMatchingAlgorithm.get_matches_recommendations(
            matching_data)
        if recommendations:
            logging.info("Submitting %s recommendations.", len(recommendations))
            self.submit_matches(recommendations)
```

Later in the script, the [on_matched_recommendations_response](matching-api-events.md#on-matched-recommendations-response) is triggered and useful information about the recommendation posted, such as seller, buyer, trading price and energy as well as the status, if successful or not, are printed in the terminal window of the user. Later, the [on_event_or_response](matching-api-events.md#on-event-or-response) is overwritten. By default we do not perform any operation in this event but the user could add some if needed.

```python
def on_matched_recommendations_response(self, data):
        pass

def on_event_or_response(self, data):
        logging.debug("Event arrived %s", data)
```

Lastly, the Matching API Script overwrites the [on_finish](matching-api-events.md#on-finish) event so that whenever the function is triggered the script stops. If the user wishes to save some information recorded within the Matching Engine SDK this would be the opportunity to export them to external files.
```python
def on_finish(self, data):
        self.is_finished = True
```
