A simple trading strategy is available in this [template script](https://github.com/gridsingularity/gsy-e-sdk/blob/master/gsy_e_sdk/setups/asset_api_template.py). This is a flexible and versatile Python script for easy modification and implementation of custom smart trading strategies. See the `TODO` flags there to see how to configure your trading strategy and extract market and asset data.

The first information to be gathered is the Market Maker price and Feed-in Tariff and calculate the average value between them. These values are required to set the boundaries of the pricing trading strategy.
```python
################################################
# GET MARKET AND ENERGY FEATURES
################################################
FiT_rate = market_info["feed_in_tariff_rate"]
Market_Maker_rate = market_info["market_maker_rate"]
Med_price = (Market_Maker_rate - FiT_rate) / 2 + FiT_rate
```

The Asset SDK Script stores energy assets information such as the energy requirements for the loads, the energy available for the PVs and the State Of Charge for the storage. This information when aggregated could be valuable when designing a smarter trading strategy.

```python
for area_uuid, area_dict in self.latest_grid_tree_flat.items():
    if "asset_info" not in area_dict or area_dict["asset_info"] is None:
        continue
    if "energy_requirement_kWh" in area_dict["asset_info"]:
        self.load_energy_requirements[area_uuid] = area_dict["asset_info"]["energy_requirement_kWh"]
    if "available_energy_kWh" in area_dict["asset_info"]:
        self.generation_energy_available[area_uuid] = area_dict["asset_info"]["available_energy_kWh"]
    if "used_storage" in area_dict["asset_info"]:
        self.storage_soc[area_uuid] = area_dict["asset_info"]["used_storage"] / (area_dict["asset_info"]["used_storage"] + area_dict["asset_info"]["free_storage"])
```
At the beginning of the script, the Exchange SDK creates a nested dictionary, containing various information for each asset (asset_strategy dictionary). First we get the name of the asset, the type (if it is a load, PV or storage) and the fees between the assets (also termed device in the code) and the market maker. The Oracle class has a function that calculates the grid fees along the path between two assets or markets in the grid: [calculate_grid_fee](https://github.com/gridsingularity/gsy-e-sdk/blob/master/gsy_e_sdk/setups/asset_api_template.py#L109). This function takes 3 arguments:

* start_market_or_asset_name: UUID of the started market/asset
* target_market_or_asset_name: UUID of the targeted market/asset
* fee_type: can either be "current_market_fee" or “last_market_fee”.

```python
for area_uuid, area_dict in self.latest_grid_tree_flat.items():
    if "asset_info" not in area_dict or area_dict["asset_info"] is None:
        continue

    self.asset_strategy[area_uuid] = {}
    self.asset_strategy[area_uuid]["asset_name"] = area_dict["area_name"]
    self.asset_strategy[area_uuid]["fee_to_market_maker"] = self.calculate_grid_fee(area_uuid, self.get_uuid_from_area_name("Market Maker"), "current_market_fee")  # TODO change the string "Market Maker" with the name defined in the grid configuration, if needed
```

These fees should be integrated in the pricing strategy in order to avoid any power outages for the loads and curtailment for the PVs. Lastly, in the asset_strategy dictionary, the pricing strategy is defined for each asset individually. This allows assets to have independent strategies depending on their information and location in the grid.

```python
self.asset_strategy[area_uuid]["fee_to_market_maker"] = self.calculate_grid_fee(area_uuid, self.get_uuid_from_area_name("Market Maker"), "current_market_fee")
```

The current pricing strategies are deterministic, representing a linear function bounded between the Feed-in Tariff-grid fee (lower boundary) and the Market Maker price + grid fee (upper boundary). Since the Exchange SDK can post up to 10 bids/offers per market slot, the strategies incrementally ramp up (bids) or down (offers) for a total of 10 prices per energy asset. The final bid/offer price is set at least 2 API available ticks before the end of the market slot length (9th and 10th tick in our case) to make sure that the bids and offers are placed before the market slot.

The load strategy, the PV strategy and the storage strategy, that can charge and discharge and therefore place bids and offers at the same time,are designed as follows.

```python
# Load strategy
if 'energy_requirement_kWh' in area_dict["asset_info"]:
    load_strategy = []
    for i in range(0, ticks):
        if i < ticks - 2:
            load_strategy.append(round(
                FiT_rate - self.asset_strategy[area_uuid]["fee_to_market_maker"] +
                (Market_Maker_rate + 2*self.asset_strategy[area_uuid]["fee_to_market_maker"] - FiT_rate) * (i / ticks), 3))
        else:
            load_strategy.append(round(
                Market_Maker_rate + self.asset_strategy[area_uuid]["fee_to_market_maker"], 3))
    self.asset_strategy[area_uuid]["buy_rates"] = load_strategy

# Generation strategy
if 'available_energy_kWh' in area_dict["asset_info"]:
    gen_strategy = []
    for i in range(0, ticks):
        if i < ticks - 2:
            gen_strategy.append(round(max(0, Market_Maker_rate + self.asset_strategy[area_uuid]["fee_to_market_maker"] -
                                (Market_Maker_rate + 2*self.asset_strategy[area_uuid]["fee_to_market_maker"] - FiT_rate) * (i / ticks)), 3))
        else:
            gen_strategy.append(round(max(0, FiT_rate - self.asset_strategy[area_uuid]["fee_to_market_maker"]), 3))
    self.asset_strategy[area_uuid]["sell_rates"] = gen_strategy

# Storage strategy
if 'used_storage' in area_dict["asset_info"]:
    batt_buy_strategy = []
    batt_sell_strategy = []
    for i in range(0, ticks):
        batt_buy_strategy.append(round(FiT_rate - self.asset_strategy[area_uuid]["fee_to_market_maker"] + (Med_price - (FiT_rate-self.asset_strategy[area_uuid]["fee_to_market_maker"])) * (i / ticks), 3))
        batt_sell_strategy.append(round(Market_Maker_rate+self.asset_strategy[area_uuid]["fee_to_market_maker"] - (Market_Maker_rate+self.asset_strategy[area_uuid]["fee_to_market_maker"] - Med_price) * (i / ticks), 3))
    self.asset_strategy[area_uuid]["buy_rates"] = batt_buy_strategy
    self.asset_strategy[area_uuid]["sell_rates"] = batt_sell_strategy
```

Later, the Asset SDK Script sends the first bid and/or offer for each energy asset. For each asset the API gets the energy requirements (load), available (storage) and energy to buy/sell (storage) through _latest_grid_tree_flat.items()_ (which is the market_info dictionary flattened). For each asset’s bid/offer, the API applies the price defined in the asset_strategy dictionary. Once all the bids/offers commands have been set, the batch is executed.

```python
################################################
# POST INITIAL BIDS AND OFFERS FOR MARKET SLOT
################################################
# takes the first element in each asset strategy to post the first bids and offers
# all bids and offers are aggregated in a single batch and then executed
# TODO how would you self-balance your managed energy assets?
for area_uuid, area_dict in self.latest_grid_tree_flat.items():
    if "asset_info" not in area_dict or area_dict["asset_info"] is None:
        continue

    # Load strategy
    if "energy_requirement_kWh" in area_dict["asset_info"] and area_dict["asset_info"]["energy_requirement_kWh"] > 0.0:
        rate = self.asset_strategy[area_uuid]["buy_rates"][0]
        energy = area_dict["asset_info"]["energy_requirement_kWh"]
        self.add_to_batch_commands.bid_energy_rate(area_uuid=area_uuid, rate=rate, energy=energy)

    # Generation strategy
    if "available_energy_kWh" in area_dict["asset_info"] and area_dict["asset_info"]["available_energy_kWh"] > 0.0:
        rate = self.asset_strategy[area_uuid]["sell_rates"][0]
        energy = area_dict["asset_info"]["available_energy_kWh"]
        self.add_to_batch_commands.offer_energy_rate(area_uuid=area_uuid, rate=rate, energy=energy)

    # Battery strategy
    if "energy_to_buy" in area_dict["asset_info"]:
        buy_energy = area_dict["asset_info"]["energy_to_buy"]
        sell_energy = area_dict["asset_info"]["energy_to_sell"]
        # Battery buy strategy
        if buy_energy > 0.0:
            buy_rate = self.asset_strategy[area_uuid]["buy_rates"][0]
            self.add_to_batch_commands.bid_energy_rate(area_uuid=area_uuid, rate=buy_rate, energy=buy_energy)
        # Battery sell strategy
        if sell_energy > 0.0:
            sell_rate = self.asset_strategy[area_uuid]["sell_rates"][0]
            self.add_to_batch_commands.offer_energy_rate(area_uuid=area_uuid, rate=sell_rate, energy=sell_energy)

response_slot = self.execute_batch_commands()
```
At each on_tick event, the Asset API can post new bids and offers, or update / delete existing ones. This allows the Exchange SDK to update their price strategy until all consumption and generation have been traded. In the following lines the Exchange SDK updates the existing bids/offers with new prices to optimize trades. The updated energy information is found in _latest_grid_tree_flat.items()_ and the prices for each bid/offer depends on the market slot progression. Once all commands are added to the batch, it is then executed.

```python
################################################
# TRIGGERS EACH TICK
################################################
"""
Places a bid or an offer 10% of the market slot progression. The amount of energy
for the bid/offer depends on the available energy of the PV, the required
energy of the load, or the amount of energy in the battery and the energy already traded.
"""
def on_tick(self, tick_info):
    i = int(float(tick_info['slot_completion'].strip('%')) / ticks)  # tick num for index

    ################################################
    # ADJUST BID AND OFFER STRATEGY (if needed)
    ################################################
    # TODO manipulate tick strategy if required
    self.asset_strategy = self.asset_strategy

    ################################################
    # UPDATE/REPLACE BIDS AND OFFERS EACH TICK
    ################################################
    for area_uuid, area_dict in self.latest_grid_tree_flat.items():
        if "asset_info" not in area_dict or area_dict["asset_info"] is None:
            continue
        # Load Strategy
        if "energy_requirement_kWh" in area_dict["asset_info"] and area_dict["asset_info"][
            "energy_requirement_kWh"] > 0.0:
            rate = self.asset_strategy[area_uuid]["buy_rates"][i]
            energy = area_dict["asset_info"]["energy_requirement_kWh"]
            self.add_to_batch_commands.bid_energy_rate(area_uuid=area_uuid, rate=rate, energy=energy)

        # Generation strategy
        if "available_energy_kWh" in area_dict["asset_info"] and area_dict["asset_info"][
            "available_energy_kWh"] > 0.0:
            rate = self.asset_strategy[area_uuid]["sell_rates"][i]
            energy = area_dict["asset_info"]["available_energy_kWh"]
            self.add_to_batch_commands.offer_energy(area_uuid=area_uuid, price=rate*energy,
                                                    energy=energy, replace_existing=True)

        # Battery strategy
        if "energy_to_buy" in area_dict["asset_info"]:
            buy_energy = area_dict["asset_info"]["energy_to_buy"] + area_dict["asset_info"]["energy_active_in_offers"]
            sell_energy = area_dict["asset_info"]["energy_to_sell"] + area_dict["asset_info"]["energy_active_in_bids"]

            # Battery buy strategy
            if buy_energy > 0.0:
                buy_rate = self.asset_strategy[area_uuid]["buy_rates"][i]
                self.add_to_batch_commands.bid_energy_rate(area_uuid=area_uuid, rate=buy_rate, energy=buy_energy)

            # Battery sell strategy
            if sell_energy > 0.0:
                sell_rate = self.asset_strategy[area_uuid]["sell_rates"][i]
                self.add_to_batch_commands.offer_energy(area_uuid=area_uuid,
                                                        price=sell_rate*sell_energy,
                                                        energy=sell_energy,
                                                        replace_existing=True)

    response_tick = self.execute_batch_commands()
```

After that, the on_event_or_response is called. By default we do not perform any operation in this event but the user could add some if needed. For instance, the user could record all the trades responses received in that event.

```python
################################################
# TRIGGERS EACH COMMAND RESPONSE AND EVENT
################################################
def on_event_or_response(self, message):
    # print("message",message)
    pass
```

Lastly, the Asset SDK Script overwrites the on_finish event so that whenever the function is triggered the script stops. If the user wishes to save some information recorded within the Exchange SDK, this would be the opportunity to export them to external files.
```python
################################################
# SIMULATION TERMINATION CONDITION
################################################
def on_finish(self, finish_info):
    # TODO export relevant information stored during the simulation (if needed)
    self.is_finished = True
```

The rest of the SDK script is used to connect to the energy assets of a running simulation/collaboration/Canary Test Network. These lines should work as is and no changes are required.

```python
################################################
# REGISTER FOR DEVICES AND MARKETS
################################################
def get_assets_name(indict: dict) -> dict:
    """
    This function is used to parse the grid tree and returned all registered assets
    wrapper for _get_assets_name
    """
    if indict == {}:
        return {}
    outdict = {"Area": [], "Load": [], "PV": [], "Storage": []}
    _get_assets_name(indict, outdict)
    return outdict


def _get_assets_name(indict: dict, outdict: dict):
    """
    Parse the collaboration / Canary Network registry
    Returns a list of the Market, Load, PV and Storage names the user is registered to
    """
    for key, value in indict.items():
        if key == "name":
            name = value
        if key == "type":
            area_type = value
        if key == "registered" and value:
            outdict[area_type].append(name)
        if 'children' in key:
            for children in indict[key]:
                _get_assets_name(children, outdict)


aggr = Oracle(aggregator_name=oracle_name)

if os.environ["API_CLIENT_RUN_ON_REDIS"] == "true":
    DeviceClient = RedisDeviceClient
    device_args = {"autoregister": True, "pubsub_thread": aggr.pubsub}
else:
    DeviceClient = RestDeviceClient
    simulation_id = os.environ["API_CLIENT_SIMULATION_ID"]
    domain_name = os.environ["API_CLIENT_DOMAIN_NAME"]
    websockets_domain_name = os.environ["API_CLIENT_WEBSOCKET_DOMAIN_NAME"]
    device_args = {"autoregister": False, "start_websocket": False}
    if automatic:
        registry = aggr.get_configuration_registry()
        registered_assets = get_assets_name(registry)
        load_names = registered_assets["Load"]
        pv_names = registered_assets["PV"]
        storage_names = registered_assets["Storage"]


def register_device_list(asset_names, asset_args, asset_uuid_map):
    for d in asset_names:
        print('Registered device:', d)
        if os.environ["API_CLIENT_RUN_ON_REDIS"] == "true":
            asset_args['area_id'] = d
        else:
            uuid = get_area_uuid_from_area_name_and_collaboration_id(simulation_id, d, domain_name)
            asset_args['area_id'] = uuid
            asset_uuid_map[uuid] = d
        asset = DeviceClient(**asset_args)
        if os.environ["API_CLIENT_RUN_ON_REDIS"] == "true":
            asset_uuid_map[asset.area_uuid] = asset.area_id
        asset.select_aggregator(aggr.aggregator_uuid)
    return asset_uuid_map


print()
print('Registering assets ...')
asset_uuid_map = {}
asset_uuid_map = register_device_list(load_names, device_args, asset_uuid_map)
asset_uuid_map = register_device_list(pv_names, device_args, asset_uuid_map)
asset_uuid_map = register_device_list(storage_names, device_args, asset_uuid_map)
aggr.device_uuid_map = asset_uuid_map
print()
print('Summary of assets registered:')
print()
print(aggr.device_uuid_map)

# loop to allow persistence
while not aggr.is_finished:
    sleep(0.5)
```
Please find the following tutorial describing the required steps to run the asset API locally and on a collaboration:

<iframe width="560" height="315" src="https://www.youtube.com/embed/oCcQ6pYFd5w" frameborder="0" allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>

*The next step is to adapt the [Asset API template](https://github.com/gridsingularity/gsy-e-sdk/blob/master/gsy_e_sdk/setups/asset_api_template.py) script developed by Grid Singularity to customize the trading strategies as you wish!*
