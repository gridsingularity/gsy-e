Asset API template scripts are flexible and versatile Python scripts that can be easily modified for the implementation of custom smart trading strategies, integration of trading preferences ([Degrees of Freedom](trading-agents-and-strategies.md#bidoffer-attributes-and-requirements-for-trading-preferences-degrees-of-freedom)), interaction with the [Settlement Market](market-types.md#settlement-market-structure) and other uses.

In this section, each script will be described along with its functionalities, in order of complexity.

##Post bids and offers to the Grid Singularity Exchange
The key functionality of the Asset API is to post bids or offers to the Grid Singularity Exchange on behalf of energy asset owners based on their preferences. A template script can be found [here](https://github.com/gridsingularity/gsy-e-sdk/blob/master/gsy_e_sdk/setups/asset_api_scripts/rest_basic_strategies.py){target=_blank}.

Users need to list the names of the assets to be connected with the Asset API, as shown in the following example. For simulations launched from the user-interface (UI), the CONNECT_TO_ALL_ASSETS parameter is available. If set to True, the Asset API connects automatically to all the assets the aggregator is connected to.

```python
# List of assets' names to be connected with the API
LOAD_NAMES = ["Load 1 L13", "Load 2 L21", "Load 3 L17"]
PV_NAMES = ["PV 1 (4kW)", "PV 3 (5kW)"]
STORAGE_NAMES = ["Tesla Powerwall 3"]

CONNECT_TO_ALL_ASSETS = True

```

The goal of this template script is to send, at each [market slot](asset-api-events.md#each-new-market-slot), a bid and/or an offer for each energy asset. This is performed by the _post_bid_offer_ function, which loops through all the assets connected with the Asset API, extracts their required or available energy and posts these values along with an associated rate for clearance and settlement by the Grid Singularity Exchange. As shown in the snippet below, the process is separated for consumption, generation and storage assets.

```python
def post_bid_offer(self):
   """Post a bid or an offer to the exchange."""
   for area_uuid, area_dict in self.latest_grid_tree_flat.items():
       asset_info = area_dict.get("asset_info")
       if not asset_info:
           continue

       # Consumption assets
       required_energy = asset_info.get("energy_requirement_kWh")
       if required_energy:
           self.add_to_batch_commands.bid_energy_rate(
               asset_uuid=area_uuid, rate=10, energy=required_energy
           )

       # Generation assets
       available_energy = asset_info.get("available_energy_kWh")
       if available_energy:
           self.add_to_batch_commands.offer_energy_rate(
               asset_uuid=area_uuid, rate=10, energy=available_energy
           )

       # Storage assets
       buy_energy = asset_info.get("energy_to_buy")
       if buy_energy:
           self.add_to_batch_commands.bid_energy_rate(
               asset_uuid=area_uuid, rate=10, energy=buy_energy
           )

       sell_energy = asset_info.get("energy_to_sell")
       if sell_energy:
           self.add_to_batch_commands.offer_energy_rate(
               asset_uuid=area_uuid, rate=10, energy=sell_energy
           )

       self.execute_batch_commands()
```
Later in the script, the _on_event_or_response_ is called. By default, the Asset API template does not perform any operation here but the user can add [events](asset-api-events.md). For instance, the user could record all the trades occurring in that event. Lastly, the script overwrites the _on_finish_ event so that when this function is triggered, the script stops. If the user wishes to save any information reported in the logs, this can be done by exporting it to an external file.

```python
def on_event_or_response(self, message):
   pass

def on_finish(self, finish_info):
   self.is_finished = True
```

The rest of the script is used to connect to the energy assets of a running [simulation](community.md)/[collaboration](collaboration.md)/[Canary Test Network](connect-ctn.md), with the purpose of actively placing bids and offers on their behalf.
```python
aggregator = Oracle(aggregator_name=ORACLE_NAME)
simulation_id = os.environ["API_CLIENT_SIMULATION_ID"]
domain_name = os.environ["API_CLIENT_DOMAIN_NAME"]
websockets_domain_name = os.environ["API_CLIENT_WEBSOCKET_DOMAIN_NAME"]
asset_args = {"autoregister": False, "start_websocket": False}
if CONNECT_TO_ALL_ASSETS:
   registry = aggregator.get_configuration_registry()
   registered_assets = get_assets_name(registry)
   LOAD_NAMES = registered_assets["Load"]
   PV_NAMES = registered_assets["PV"]
   STORAGE_NAMES = registered_assets["Storage"]


def register_asset_list(asset_names: List, asset_params: Dict, asset_uuid_map: Dict) -> Dict:
   """Register the provided list of assets with the aggregator."""
   for asset_name in asset_names:
       print("Registered asset:", asset_name)
       uuid = get_area_uuid_from_area_name_and_collaboration_id(
           simulation_id, asset_name, domain_name
       )
       asset_params["asset_uuid"] = uuid
       asset_uuid_map[uuid] = asset_name
       asset = RestAssetClient(**asset_params)
       asset.select_aggregator(aggregator.aggregator_uuid)
   return asset_uuid_map


print()
print("Registering assets ...")
asset_uuid_mapping = {}
asset_uuid_mapping = register_asset_list(LOAD_NAMES + PV_NAMES + STORAGE_NAMES,
                                        asset_args, asset_uuid_mapping)
print()
print("Summary of assets registered:")
print()
print(asset_uuid_mapping)

# loop to allow persistence
while not aggregator.is_finished:
   sleep(0.5)
```

For simulations run in the backend, a similar script is available [here](https://github.com/gridsingularity/gsy-e-sdk/blob/master/gsy_e_sdk/setups/asset_api_scripts/redis_bid_offer_posting.py){target=_blank}.

## Implement trading strategies
One of the main functionalities provided by the Asset API is to implement customized trading strategies. The Asset API script stores energy assets information such as the energy requirements for the [loads](consumption.md), the energy available for the [PVs](solar-panels.md) and the State of Charge for the [storage](battery.md). This information when aggregated could be valuable when designing a smarter trading strategy. A template script can be found [here](https://github.com/gridsingularity/gsy-e-sdk/blob/master/gsy_e_sdk/setups/asset_api_scripts/rest_basic_strategies.py).

At the beginning of the _[on_market_slot](asset-api-events.md#each-new-market-slot)_ event, the script generates the trading strategies (in the _build_strategies_ function). The [Market Maker](assets-installation.md#market-maker) price and the Feed-in Tariff values are required to set the pricing boundaries for the trading strategy.

```python
fit_rate = market_info["feed_in_tariff_rate"]
market_maker_rate = market_info["market_maker_rate"]
med_price = (market_maker_rate - fit_rate) / 2 + fit_rate
```

Then, the script creates the _asset_strategy_ dictionary, which contains various information for each asset, such as its name, its type (load, PV or storage) and the [grid fees](grid-fee-accounting.md) between the assets and the market maker. To calculate the grid fees between two assets or markets in the grid, the  _[calculate_grid_fee](https://github.com/gridsingularity/gsy-e-sdk/blob/3dea1f42e283736ccbaaac6e51f4127e2bbfb020/gsy_e_sdk/aggregator.py#L194)_ function is used,which takes 3 arguments:

* _start_market_or_asset_name_: UUID of the started market/asset
* _target_market_or_asset_name_: UUID of the targeted market/asset
* _fee_type_: can either be "current_market_fee" or “last_market_fee”

The fees are integrated in the pricing strategy in order to avoid any power outages for the loads or PV curtailment.

```python
for area_uuid, area_dict in self.latest_grid_tree_flat.items():
   if "asset_info" not in area_dict or area_dict["asset_info"] is None:
       continue
   self.asset_strategy[area_uuid] = {}
   self.asset_strategy[area_uuid]["asset_name"] = area_dict["area_name"]
   self.asset_strategy[area_uuid][
       "fee_to_market_maker"
   ] = self.calculate_grid_fee(
       area_uuid,
       self.get_uuid_from_area_name("Market Maker"),
       "current_market_fee",
   )
```
Lastly, in the _asset_strategy_ dictionary, the pricing strategy is defined for each asset individually. This allows assets to have independent strategies depending on the available market information and their location in the grid.

The current pricing strategies are deterministic, representing a linear function bounded between the Feed-in Tariff - grid fee (lower boundary) and the Market Maker price + grid fee (upper boundary). Since the Asset API can post bids/offers at every tick, the number of posts is limited to the number of ticks in the market slot. In the template strategy, bids are ramped up and offers are ramped down for a total of 10 prices per energy asset. This can be configured by setting the `TICK_DISPATCH_FREQUENCY_PERCENT` parameter (at the top of the script). The final bid/offer price is set at 80% market slot completion in order for the update to be visible by all other market participants. The load strategy, the PV strategy and the storage strategy, representing assets that can charge and discharge and therefore place bids and offers at the same time, are designed as follows.

```python
# Consumption strategy
if "energy_requirement_kWh" in area_dict["asset_info"]:
   load_strategy = []
   for tick in range(0, TICKS):
       if tick < TICKS - 2:
           buy_rate = (fit_rate -
                       self.asset_strategy[area_uuid]["fee_to_market_maker"] +
                       (market_maker_rate +
                        2 * self.asset_strategy[area_uuid]["fee_to_market_maker"] -
                        fit_rate) * (tick / TICKS)
                       )
           load_strategy.append(buy_rate)
       else:
           buy_rate = market_maker_rate + (
               self.asset_strategy[area_uuid]["fee_to_market_maker"])
           load_strategy.append(buy_rate)
   self.asset_strategy[area_uuid]["buy_rates"] = load_strategy

# Generation strategy
if "available_energy_kWh" in area_dict["asset_info"]:
   gen_strategy = []
   for tick in range(0, TICKS):
       if tick < TICKS - 2:
           sell_rate = (market_maker_rate +
                        self.asset_strategy[area_uuid]["fee_to_market_maker"] -
                        (market_maker_rate +
                         2 * self.asset_strategy[area_uuid]["fee_to_market_maker"] -
                         fit_rate) * (tick / TICKS)
                        )
           gen_strategy.append(max(0, sell_rate))
       else:
           sell_rate = fit_rate - (
               self.asset_strategy[area_uuid]["fee_to_market_maker"])
           gen_strategy.append(max(0, sell_rate))
   self.asset_strategy[area_uuid]["sell_rates"] = gen_strategy

# Storage strategy
if "used_storage" in area_dict["asset_info"]:
   batt_buy_strategy = []
   batt_sell_strategy = []
   for tick in range(0, TICKS):
       buy_rate = (fit_rate -
                   self.asset_strategy[area_uuid]["fee_to_market_maker"] +
                   (med_price -
                    (fit_rate -
                     self.asset_strategy[area_uuid]["fee_to_market_maker"]
                     )
                    ) * (tick / TICKS)
                   )
       batt_buy_strategy.append(buy_rate)
       sell_rate = (market_maker_rate +
                    self.asset_strategy[area_uuid]["fee_to_market_maker"] -
                    (market_maker_rate +
                     self.asset_strategy[area_uuid]["fee_to_market_maker"] -
                     med_price) * (tick / TICKS)
                    )
       batt_sell_strategy.append(sell_rate)
   self.asset_strategy[area_uuid]["buy_rates"] = batt_buy_strategy
   self.asset_strategy[area_uuid]["sell_rates"] = batt_sell_strategy
```

At each _on_tick_ event, the Asset API will post new bids and offers, or update / delete existing ones. This allows the Exchange SDK to update their price strategy until all consumption and generation have been traded. In the following lines the Exchange SDK updates the existing bids/offers with new prices to optimize trades. The updated energy information is found in _latest_grid_tree_flat.items()_ and the prices for each bid/offer depend on the market slot progression. All the commands are then executed.

```python
def post_bid_offer(self, rate_index=0):
   """Post a bid or an offer to the exchange."""
   for area_uuid, area_dict in self.latest_grid_tree_flat.items():
       asset_info = area_dict.get("asset_info")
       if not asset_info:
           continue

       # Consumption assets
       required_energy = asset_info.get("energy_requirement_kWh")
       if required_energy:
           rate = self.asset_strategy[area_uuid]["buy_rates"][rate_index]
           self.add_to_batch_commands.bid_energy_rate(
               asset_uuid=area_uuid, rate=rate, energy=required_energy
           )

       # Generation assets
       available_energy = asset_info.get("available_energy_kWh")
       if available_energy:
           rate = self.asset_strategy[area_uuid]["sell_rates"][rate_index]
           self.add_to_batch_commands.offer_energy_rate(
               asset_uuid=area_uuid, rate=rate, energy=available_energy
           )

       # Storage assets
       buy_energy = asset_info.get("energy_to_buy")
       if buy_energy:
           buy_rate = self.asset_strategy[area_uuid]["buy_rates"][rate_index]
           self.add_to_batch_commands.bid_energy_rate(
               asset_uuid=area_uuid, rate=buy_rate, energy=buy_energy
           )

       sell_energy = asset_info.get("energy_to_sell")
       if sell_energy:
           sell_rate = self.asset_strategy[area_uuid]["sell_rates"][rate_index]
           self.add_to_batch_commands.offer_energy_rate(
               asset_uuid=area_uuid, rate=sell_rate, energy=sell_energy
           )

       self.execute_batch_commands()
```

The rest of the script functionality has been covered in the [previous section](setup-configuration.md). For simulations run in the backend, a similar script is available [here](https://github.com/gridsingularity/gsy-e-sdk/blob/master/gsy_e_sdk/setups/asset_api_scripts/redis_basic_strategies.py){target=_blank}.

##Introduce trading preferences with the Degrees of Freedom

With the Asset API, users also have the option to specify trading preferences for each asset, such as preferred trading partners, energy type, energy amount and rate. An example of such a script can be found [here](https://github.com/gridsingularity/gsy-e-sdk/blob/master/gsy_e_sdk/setups/asset_api_scripts/degrees_of_freedom.py){target=_blank}. These preferences are also known as requirements and attributes or “degrees of freedom”, as explained [here](trading-agents-and-strategies.md#bidoffer-attributes-and-requirements-for-trading-preferences-degrees-of-freedom).

Requirements are uploaded to the template script via a JSON file (an example can be found [here](https://github.com/gridsingularity/gsy-e-sdk/blob/master/gsy_e_sdk/setups/asset_api_scripts/resources/requirements.json){target=_blank}), which has the following structure:

```python
{
   "Load 3 L17":[
       {
           "Trading Partners": ["PV 9 (15kW)"],
           "Energy Types": [],
           "Energy": "None",
           "Rate": "None"
   }
   ],
   "Load 2 L21":[
       {
           "Trading Partners": ["PV 5 (10kW)"],
           "Energy Types": [],
           "Energy": 10,
           "Rate": 3
   }
   ],
   "Load 1 L13":[
       {
           "Trading Partners": [],
           "Energy Types": [],
           "Energy": "None",
           "Rate": "None"
   }
]
}


```

In this example it is shown how, for each load, the four above mentioned requirements are listed and specified in value. It is also possible not to set any specific requirement to an asset, as for Load 1 L13. If, for example, “Energy” and “Rate” are set to None, the default energy and rate values from the template trading strategies are assigned. At [each market slot](asset-api-events.md#each-new-market-slot), the Asset API loads and reads the information contained in this JSON file with the following function:

```python
def read_requirements(self):
   """Load the JSON file containing the list of requirements for each asset."""
   with open(
       os.path.join(module_dir, "resources/requirements.json"),
       "r",
       encoding="utf-8",
   ) as file:
       self.degrees_of_freedom = json.load(file)

```
Subsequently, a bid with the associated requirements is posted to the Exchange (for more on how to post bids and offers please see [here](asset-api-template-script.md).) The requirements uploaded through the JSON file must be converted to the correct format ahead of submission to the Exchange. To do so, the _build_requirements_dict_ function is used:

```python
def build_requirements_dict(self, rate, energy, area_name):
   """Return a dictionary with the requirements of the asset."""
   asset_dof_list = self.degrees_of_freedom[area_name]
   for asset_dof in asset_dof_list:
       id_trading_partners_list = get_partner_ids(asset_dof["Trading Partners"])
       energy_types_list = asset_dof["Energy Types"]
       energy_requirement = (
           energy
           if asset_dof["Energy"] == "None"
           else min(asset_dof["Energy"], energy)
       )
       rate_requirement = (
           rate if asset_dof["Rate"] == "None" else asset_dof["Rate"]
       )
       requirements = [
           {
               "trading_partners": id_trading_partners_list,
               "energy_type": energy_types_list,
               "energy": energy_requirement,
               "price": rate_requirement * energy_requirement,
           }
       ]
   return requirements
```
The rest of the script functionality has been covered in the [previous section](setup-configuration.md). It is important to note that currently there is no available template script for introducing degrees of freedom from the UI, but solely from the [backend](setup-configuration.md).

##Send live data to a Canary Test Network
As noted [here](send-data-exchange-sdk.md), the Asset API has the functionality to send live data to Grid Singularity [Canary Test Network](connect-ctn.md). A template script can be found [here](https://github.com/gridsingularity/gsy-e-sdk/blob/master/gsy_e_sdk/setups/asset_api_scripts/canary_network_live_data.py). To do so, at each [market slot](asset-api-events.md#each-new-market-slot), forecast for the next 15 minutes are sent through the following function:

```python
def send_forecasts(self, market_info):
   """Send forecasts of the next market slot to the exchange."""
   forecast_market_slot = (
       from_format(market_info["market_slot"], DATE_TIME_FORMAT)
       .add(minutes=15)
       .format(DATE_TIME_FORMAT)
   )
   # pylint: disable=unused-variable
   for area_uuid, area_dict in self.latest_grid_tree_flat.items():
       asset_info = area_dict.get("asset_info")
       if not asset_info:
           continue

       # Consumption assets
       if "energy_requirement_kWh" in asset_info:
           asset_name = area_dict["area_name"]
           globals()[f"{asset_name}"].set_energy_forecast(
               energy_forecast_kWh={forecast_market_slot: 1.2},
               do_not_wait=False,
           )

       # Generation assets
       if "available_energy_kWh" in asset_info:
           asset_name = area_dict["area_name"]
           globals()[f"{asset_name}"].set_energy_forecast(
               energy_forecast_kWh={forecast_market_slot: 0.86},
               do_not_wait=False,
           )
       self.execute_batch_commands()
```
The _forecast_market_slot_, namely the marker slot at which the forecasted value is sent, is first retrieved by the _market_info_ dictionary. Then, the _set_energy_forecast_ function is used to send consumption / generation forecasted values to the Grid Singularity Exchange. In this example, 1.2 kWh are sent as consumption forecasts and 0.86 kWh are sent as generation forecasts.

The rest of the script functionality has been covered in the [previous section](setup-configuration.md).

##Post energy deviations in the Settlement Market

Finally, the Asset API can also be used to post energy deviations between forecasts (namely the values of consumption or generation that an asset was expected to consume or produce) and measurements (namely the actual consumption or generation values) in the [Settlement Market](market-types.md#settlement-market-structure). A template script can be found [here](https://github.com/gridsingularity/gsy-e-sdk/blob/master/gsy_e_sdk/setups/asset_api_scripts/redis_settle_energy_deviations.py).

As noted in the previous section, users can send forecasts (generated by assets or other data source) to the Grid Singularity Exchange by  using the Asset API. To settle energy deviations in the Settlement Market, further action is needed, which is to send measurements to the Exchange at each market slot by using the following function:

```python
def send_measurements(self, market_info):
   """Send measurements for the current market slot to the exchange."""
   # pylint: disable=unused-variable
   for area_uuid, area_dict in self.latest_grid_tree_flat.items():
       if "asset_info" not in area_dict or area_dict["asset_info"] is None:
           continue
       # Consumption assets
       if "energy_requirement_kWh" in area_dict["asset_info"]:
           self.add_to_batch_commands.set_energy_measurement(
               asset_uuid=area_uuid,
               energy_measurement_kWh={market_info["market_slot"]: 1.23},
           )
       # Generation assets
       if "available_energy_kWh" in area_dict["asset_info"]:
           self.add_to_batch_commands.set_energy_measurement(
               asset_uuid=area_uuid,
               energy_measurement_kWh={market_info["market_slot"]: 0.87},
           )
```
As shown in the snippet above, _set_energy_measurement_ is used to send values to the Exchange which, in this example, are sent to the current market slot.

Later, in _settle_energy_deviation_, the Asset API computes the difference between the forecast and measured values, called in the script _unsettled_deviation_.  Depending on whether this value is positive or negative, a bid or an offer will be posted in the Settlement Market. The rate, as well as the time slot for order placement can be arbitrarily set by the user. Below is the snippet of the described function:

```python
def settle_energy_deviations(self):
   """Post the energy deviations between forecasts
   and measurements in the Settlement market."""
   for area_uuid, area_dict in self.latest_grid_tree_flat.items():
       if not area_dict.get("asset_info"):
           continue
       time_slot = (
           list(area_dict["asset_info"]["unsettled_deviation_kWh"].keys())[-1])
       unsettled_deviation = area_dict["asset_info"][
           "unsettled_deviation_kWh"
       ].get(time_slot)
       if unsettled_deviation > 0:
           self.add_to_batch_commands.bid_energy_rate(
               asset_uuid=area_uuid,
               rate=5,
               energy=unsettled_deviation,
               time_slot=time_slot,
           )
       if unsettled_deviation < 0:
           self.add_to_batch_commands.offer_energy_rate(
               asset_uuid=area_uuid,
               rate=10,
               energy=abs(unsettled_deviation),
               time_slot=time_slot,
           )
```
The rest of the script functionality has been covered in the [previous section](setup-configuration.md). It is important to note that currently there is no available template script for interacting with the Settlement Market from the UI, but solely from the [backend](setup-configuration.md).

The next step is to adapt the Asset API template scripts developed by Grid Singularity to customize your trading strategies, whether to send live data to the Grid Singularity [Canary Test Network](connect-ctn.md) or to interact with the [Settlement Market](market-types.md#settlement-market-structure).
