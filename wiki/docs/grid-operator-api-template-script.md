A Grid Operator API template script is available [here](https://github.com/gridsingularity/gsy-e-sdk/blob/master/gsy_e_sdk/setups/grid_operator_api_template.py). This is a flexible and versatile Python script for easy modification and implementation of custom grid fee strategies. See the `TODO` flags there to see how to configure your grid fee strategy and extract market data.

In this script two template strategies are available:

###Time-of-Use (ToU)

This is a strategy where grid fee is applied depending on the **time of the day** (hours and minutes) regardless of the market conditions. After analysing import and export patterns of their client, grid operators can create a time-based curve, increasing fees at peak predicted times (e.g. morning and dinner time).

Here is an example of ToU strategy that was used by the DSOs in one of the experiments at [Odyssey hackathon](https://gridsingularity.medium.com/energy-singularity-challenge-2020-testing-novel-grid-fee-models-and-intelligent-peer-to-peer-6a0d715a9063).

![alt_text](img/grid-operator-api-2.png)

###Aziiz pricing

The Aziiz model is using past market information to determine the next grid fee. The model looks at **past imports and exports** on a specific market, applies a moving average and then based on this number sets the next grid fee for that market. This model has the advantage of integrating market conditions into its strategy. For instance if past market slots experienced high imports, the model will increase fees in the relevant market to incentivise market participants to contain the energy within that area.

###Script Configuration

At the start of the SDK Script, the user needs to specify the markets she/he wishes to connect and manage as well as the [Oracle name](asset-api-events.md).

```python
################################################
# CONFIGURATIONS
################################################
automatic = True

# List of market the Grid Operators connect to
market_names = ["Grid", "Community"]  # TODO list the market names as they are in the collaboration

# Name of your aggregator
oracle_name = "dso
```

Right after that, the user can select the strategy to use (Time of Use or Aziiz model). To select the Time of Use strategy, you have to set TimeOfUse to True and Aziiz to False. On the other hand, to select the Aziiz model, the user has to set TimeOfUse to False and Aziiz to True.
If the Aziiz model is selected, the user can tune parameters such as applying the moving average and specifying the number of past market slots to average.

```python
# Grid tariff selection
TimeOfUse = True  # TODO Activate the Time of Use model if set to True
Aziiz = False  # TODO Activate the Aziiz model if set to True
moving_average_peak = True  # Perform a moving average of the last #look_back ptu (for the Aziiz tariff only)
look_back = 4  # Number of past markets slots to apply the moving average (for the Aziiz tariff only)

slot_length = 15  # leave as is


def fee_strategy():
    if TimeOfUse:
        market_prices = pd.read_excel(os.path.join(current_dir,"resources/ToU.xlsx"))  # TODO upload an Excel/CSV file with prices of every market at each time slot (based on given template)

        planned_fee = {}
        for i in range(len(market_prices)):
            for j in market_names:
                planned_fee.update({(str(market_prices["Time"][i])[0:5], j): market_prices[j][i]})

    if Aziiz:
        market_prices = pd.ExcelFile(os.path.join(current_dir, "resources/Aziiz.xlsx"))  # TODO upload an Excel/CSV file with thresholds and fees of every market (based on given template)

    return market_prices, planned_fee
```

For both strategies, the script reads an Excel file to adjust the grid fees ([ToU.xlsx](https://github.com/gridsingularity/gsy-e-sdk/blob/master/gsy_e_sdk/setups/resources/ToU.xlsx) and [Aziiz.xlsx](https://github.com/gridsingularity/gsy-e-sdk/blob/master/gsy_e_sdk/setups/resources/Aziiz.xlsx)). In ToU.xlsx the user can define the grid fees for each market she/he manages for every quarter hours of the day.

![alt_text](img/grid-operator-api-3.png)

In Aziiz.xlsx grid fees can be set for every peak import/export thresholds for each market. The Aziiz strategy will compare the average of the last markets’ peak import/export to the threshold. If the average is lower than the threshold the relevant grid fee will be applied (for instance on the figure below if the average peak is equal to 22kWh, the next grid fee will be 3 cents/KWh. Each sheet’s name represents the market connected to.

![alt_text](img/grid-operator-api-4.png)

On_market_slot event is used to gather market statistics and set the grid fees for the next market slot. In the first part, the Grid Operator API is requesting market statistics from the simulation.

```python
################################################
# STORE MARKET INFORMATION
################################################
for area_uuid, area_dict in self.latest_grid_tree_flat.items():
    if area_dict["area_name"] in market_names:
        self.add_to_batch_commands.last_market_dso_stats(area_uuid)

self.dso_stats_response = self.execute_batch_commands()
```

Later in the script, the API is storing some of the relevant market data to local variables, easier to manipulate.

```python
for area_uuid, area_dict in self.latest_grid_tree_flat.items():
            if area_dict["area_name"] in market_names:
                self.last_market_fee[area_dict["area_name"]] = area_dict["last_market_fee"]
                self.current_market_fee[area_dict["area_name"]] = area_dict["current_market_fee"]

        for uuid, market_event in self.dso_stats_response["responses"].items():
            # Store data from market info into variables - these variables are updated in a way that always just store the current/most updated values
            self.min_trade_rate[market_event[0]['name']] = market_event[0]["market_stats"]["min_trade_rate"]
            self.avg_trade_rate[market_event[0]['name']] = market_event[0]["market_stats"]["avg_trade_rate"]
            self.max_trade_rate[market_event[0]['name']] = market_event[0]["market_stats"]["max_trade_rate"]
            self.median_trade_rate[market_event[0]['name']] = market_event[0]["market_stats"]["median_trade_rate"]
            self.total_traded_energy_kWh[market_event[0]['name']] = market_event[0]["market_stats"]["total_traded_energy_kWh"]
            self.self_sufficiency[market_event[0]['name']] = market_event[0]["market_stats"]["self_sufficiency"]
            self.self_consumption[market_event[0]['name']] = market_event[0]["market_stats"]["self_consumption"]
            self.import_kWh[market_event[0]['name']] = market_event[0]["market_stats"]['area_throughput']['import']
            self.export_kWh[market_event[0]['name']] = market_event[0]["market_stats"]['area_throughput']['export']
            try:
                self.balance[market_event[0]['name']] = self.import_kWh[market_event[0]['name']] - self.export_kWh[market_event[0]['name']]
            except:
                self.balance[market_event[0]['name']] = 0

        self.balance_hist = self.balance_hist.append(self.balance,ignore_index=True)  # DataFrame that gets updated and grows at each market slot and contains the balance (import - export) for the areas

        # Print information in the terminal
        print('LAST MARKET STATISTICS')

        last_market_table1 = []
        for i in range(len(market_names)):
            keys_list = list(self.total_traded_energy_kWh.keys())
            values_list = list(self.total_traded_energy_kWh.values())
            min_values_list = list(self.min_trade_rate.values())
            avg_values_list = list(self.avg_trade_rate.values())
            med_values_list = list(self.median_trade_rate.values())
            max_values_list = list(self.max_trade_rate.values())

            # Print None values as 0
            values_list = [0 if x is None else x for x in values_list]
            min_values_list = [0 if x is None else x for x in min_values_list]
            avg_values_list = [0 if x is None else x for x in avg_values_list]
            med_values_list = [0 if x is None else x for x in med_values_list]
            max_values_list = [0 if x is None else x for x in max_values_list]

            last_market_table1.append(
                [keys_list[i], values_list[i], min_values_list[i], avg_values_list[i], med_values_list[i],
                 max_values_list[i]])

        last_market_headers1 = ["Markets", "Total energy traded [kWh]", "Min trade rate [€cts/Kwh]",
                                "Avg trade rate [€cts/Kwh]", "Med trade rate [€cts/Kwh]", "Max trade rate [€cts/Kwh]"]
        print(tabulate(last_market_table1, last_market_headers1, tablefmt="fancy_grid"))

        last_market_table2 = []
        for i in range(len(market_names)):
            keys_list = list(self.total_traded_energy_kWh.keys())
            ss_values_list = list(self.self_sufficiency.values())
            sc_values_list = list(self.self_consumption.values())
            energy_imp_values_list = list(self.import_kWh.values())
            energy_exp_values_list = list(self.export_kWh.values())
            last_fee_values_list = list(self.last_market_fee.values())
            # Print None values as 0
            ss_values_list = [0 if x is None else x for x in ss_values_list]
            sc_values_list = [0 if x is None else x for x in sc_values_list]
            energy_imp_values_list = [0 if x is None else x for x in energy_imp_values_list]
            energy_exp_values_list = [0 if x is None else x for x in energy_exp_values_list]
            last_fee_values_list = [0 if x is None else x for x in last_fee_values_list]

            last_market_table2.append([keys_list[i], ss_values_list[i], sc_values_list[i], energy_imp_values_list[i],
                                       energy_exp_values_list[i], last_fee_values_list[i]])

        last_market_headers2 = ["Markets", "Self sufficiency [%]", "Self consumption [%]", "Energy import [kWh]",
                                "Energy export [kWh]", "Last fee [€cts/Kwh]"]
        print(tabulate(last_market_table2, last_market_headers2, tablefmt="fancy_grid"))

        ################################################
        # SET NEW GRID FEE
        ################################################
        for area_uuid, area_dict in self.latest_grid_tree_flat.items():

            if area_dict["area_name"] in market_names:
                ###################################################################
                # TIME OF USE STRATEGY
                ###################################################################
                if TimeOfUse:
                    self.next_market_fee[area_dict["area_name"]] = self.scheduled_fee(self.market_time, planned_fee,
                                                                                      area_dict["area_name"])

                ###################################################################
                # AZIIZ STRATEGY
                ###################################################################
                if Aziiz:

                    if moving_average_peak:
                        self.max_ext_energy_kWh = abs(self.balance_hist[area_dict["area_name"]].iloc[
                                                      -look_back:].mean())  # Calculate the absolute moving average of the net balance by looking back at 4 markets
                    else:
                        self.max_ext_energy_kWh = max(self.import_kWh[area_dict["area_name"]], self.export_kWh[
                            area_dict[
                                "area_name"]])  # Calculate the max between the import and export of the defined market

                    individual_market_prices = pd.read_excel(market_prices, area_dict["area_name"])  # Select the market in the file

                    for k in range(len(individual_market_prices)):
                        if self.max_ext_energy_kWh <= individual_market_prices["Threshold"][k]:  # if the peak is lower than this value, the following grid fee will be applied. If the max is higher, it will go to the lower elif condition
                            self.next_market_fee[area_dict["area_name"]] = individual_market_prices["Grid fee"][
                                k]  # new grid fee
                            break
                        else:
                            self.next_market_fee[area_dict[
                                "area_name"]] = 2000  # TODO set the last value if all the previous ones are not fulfilled

                self.add_to_batch_commands.grid_fees(area_uuid=area_uuid,fee_cents_kwh=self.next_market_fee[area_dict["area_name"]])

        next_fee_response = self.execute_batch_commands()  # send batch command

        print()
        print('CURRENT AND NEXT MARKET FEES')

        current_market_table = []
        for i in range(len(market_names)):
            keys_list = list(self.current_market_fee.keys())
            current_fee_values_list = list(self.current_market_fee.values())
            next_fee_values_list = list(self.next_market_fee.values())

            current_fee_values_list = [0 if x is None else x for x in current_fee_values_list]
            next_fee_values_list = [0 if x is None else x for x in next_fee_values_list]

            current_market_table.append([keys_list[i], current_fee_values_list[i], next_fee_values_list[i]])

        current_market_headers = ["Markets", "Current fee [€cts/kWh]", "Next fee [€cts/kWh]"]
        print(tabulate(current_market_table, current_market_headers, tablefmt="fancy_grid"))

    ################################################
    # TRIGGERS EACH COMMAND RESPONSE AND EVENT
    ################################################
    def on_event_or_response(self, message):
        # print("message",message)
        pass

    ################################################
    # SIMULATION TERMINATION CONDITION
    ################################################
    def on_finish(self, finish_info):
        # TODO export relevant information stored during the simulation (if needed)
        self.is_finished = True


################################################
# REGISTER FOR MARKETS
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
    Returns a list of the Market, Load, PV and Storage nodes the user is registered to
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


# Code to create the market aggregator and connect to the relevant simulation. Keep it as is
if os.environ["API_CLIENT_RUN_ON_REDIS"] == "true":
    MarketClient = RedisMarketClient
    market_args = {"autoregister": True}
    aggr = Oracle(aggregator_name=oracle_name)

else:
    MarketClient = RestMarketClient
    simulation_id = os.environ["API_CLIENT_SIMULATION_ID"]
    domain_name = os.environ["API_CLIENT_DOMAIN_NAME"]
    websockets_domain_name = os.environ["API_CLIENT_WEBSOCKET_DOMAIN_NAME"]
    market_args = {"simulation_id": simulation_id,
                   "domain_name": domain_name, "websockets_domain_name": websockets_domain_name}

    aggr = Oracle(aggregator_name=oracle_name, **market_args)
    if automatic:
        registry = aggr.get_configuration_registry()
        market_names = get_assets_name(registry)["Area"]

market_prices, planned_fee = fee_strategy()

print()
print('Connecting to markets ...')

for i in market_names:
    if os.environ["API_CLIENT_RUN_ON_REDIS"] == "true":
        market_registered = RedisMarketClient(area_id=i)
    else:
        market_uuid = get_area_uuid_from_area_name_and_collaboration_id(market_args["simulation_id"], i, market_args["domain_name"])
        market_args["area_id"] = market_uuid
        market_registered = RestMarketClient(**market_args)
    selected = market_registered.select_aggregator(aggr.aggregator_uuid)
    print("----> Connected to ", i)
    sleep(0.3)

print(aggr.device_uuid_list)

# loop to allow persistence
while not aggr.is_finished:
    sleep(0.5)
```

In the following lines, to improve the API monitoring, the script is printing relevant data in the terminal:

![alt_text](img/grid-operator-api-5.png)

```python
# Print information in the terminal
print('LAST MARKET STATISTICS')

last_market_table1 = []
for i in range(len(market_names)):
    keys_list = list(self.total_traded_energy_kWh.keys())
    values_list = list(self.total_traded_energy_kWh.values())
    min_values_list = list(self.min_trade_rate.values())
    avg_values_list = list(self.avg_trade_rate.values())
    med_values_list = list(self.median_trade_rate.values())
    max_values_list = list(self.max_trade_rate.values())

    # Print None values as 0
    values_list = [0 if x is None else x for x in values_list]
    min_values_list = [0 if x is None else x for x in min_values_list]
    avg_values_list = [0 if x is None else x for x in avg_values_list]
    med_values_list = [0 if x is None else x for x in med_values_list]
    max_values_list = [0 if x is None else x for x in max_values_list]

    last_market_table1.append(
        [keys_list[i], values_list[i], min_values_list[i], avg_values_list[i], med_values_list[i],
         max_values_list[i]])

last_market_headers1 = ["Markets", "Total energy traded [kWh]", "Min trade rate [€cts/Kwh]",
                        "Avg trade rate [€cts/Kwh]", "Med trade rate [€cts/Kwh]", "Max trade rate [€cts/Kwh]"]
print(tabulate(last_market_table1, last_market_headers1, tablefmt="fancy_grid"))

last_market_table2 = []
for i in range(len(market_names)):
    keys_list = list(self.total_traded_energy_kWh.keys())
    ss_values_list = list(self.self_sufficiency.values())
    sc_values_list = list(self.self_consumption.values())
    energy_imp_values_list = list(self.import_kWh.values())
    energy_exp_values_list = list(self.export_kWh.values())
    last_fee_values_list = list(self.last_market_fee.values())
    # Print None values as 0
    ss_values_list = [0 if x is None else x for x in ss_values_list]
    sc_values_list = [0 if x is None else x for x in sc_values_list]
    energy_imp_values_list = [0 if x is None else x for x in energy_imp_values_list]
    energy_exp_values_list = [0 if x is None else x for x in energy_exp_values_list]
    last_fee_values_list = [0 if x is None else x for x in last_fee_values_list]

    last_market_table2.append([keys_list[i], ss_values_list[i], sc_values_list[i], energy_imp_values_list[i],
                               energy_exp_values_list[i], last_fee_values_list[i]])

last_market_headers2 = ["Markets", "Self sufficiency [%]", "Self consumption [%]", "Energy import [kWh]",
                        "Energy export [kWh]", "Last fee [€cts/Kwh]"]
print(tabulate(last_market_table2, last_market_headers2, tablefmt="fancy_grid"))
```

In the next section, the script applies the grid fee depending on the fee strategy chosen here. If the Time of Use was set, the markets’ grid fee is set based on the ToU excel file. If the Aziiz model was chosen the next fee is defined based on the Aziiz excel file. Additionally, if the peak import/export is higher than all threshold defined in the excel sheets this line sets the next fee as 2000cts/kWh. All the fees are added to the batch command and then executed.

```python
################################################
# SET NEW GRID FEE
################################################
for area_uuid, area_dict in self.latest_grid_tree_flat.items():

    if area_dict["area_name"] in market_names:
        ###################################################################
        # TIME OF USE STRATEGY
        ###################################################################
        if TimeOfUse:
            self.next_market_fee[area_dict["area_name"]] = self.scheduled_fee(self.market_time, planned_fee,
                                                                              area_dict["area_name"])

        ###################################################################
        # AZIIZ STRATEGY
        ###################################################################
        if Aziiz:

            if moving_average_peak:
                self.max_ext_energy_kWh = abs(self.balance_hist[area_dict["area_name"]].iloc[
                                              -look_back:].mean())  # Calculate the absolute moving average of the net balance by looking back at 4 markets
            else:
                self.max_ext_energy_kWh = max(self.import_kWh[area_dict["area_name"]], self.export_kWh[
                    area_dict[
                        "area_name"]])  # Calculate the max between the import and export of the defined market

            individual_market_prices = pd.read_excel(market_prices, area_dict["area_name"])  # Select the market in the file

            for k in range(len(individual_market_prices)):
                if self.max_ext_energy_kWh <= individual_market_prices["Threshold"][k]:  # if the peak is lower than this value, the following grid fee will be applied. If the max is higher, it will go to the lower elif condition
                    self.next_market_fee[area_dict["area_name"]] = individual_market_prices["Grid fee"][
                        k]  # new grid fee
                    break
                else:
                    self.next_market_fee[area_dict[
                        "area_name"]] = 2000  # TODO set the last value if all the previous ones are not fulfilled

        self.add_to_batch_commands.grid_fees(area_uuid=area_uuid,fee_cents_kwh=self.next_market_fee[area_dict["area_name"]])

next_fee_response = self.execute_batch_commands()  # send batch command
```
In the following lines, the script is printing the current fee and next fee for each market.

![alt_text](img/grid-operator-api-6.png)

```python
print()
        print('CURRENT AND NEXT MARKET FEES')

        current_market_table = []
        for i in range(len(market_names)):
            keys_list = list(self.current_market_fee.keys())
            current_fee_values_list = list(self.current_market_fee.values())
            next_fee_values_list = list(self.next_market_fee.values())

            current_fee_values_list = [0 if x is None else x for x in current_fee_values_list]
            next_fee_values_list = [0 if x is None else x for x in next_fee_values_list]

            current_market_table.append([keys_list[i], current_fee_values_list[i], next_fee_values_list[i]])

        current_market_headers = ["Markets", "Current fee [€cts/kWh]", "Next fee [€cts/kWh]"]
        print(tabulate(current_market_table, current_market_headers, tablefmt="fancy_grid"))
```

Later, the on_event_or_response is overwritten. By default we do not perform any operation in this event but the user could add some if needed. For instance the user could record all the grid fee change responses received in that event.

```python
################################################
# TRIGGERS EACH COMMAND RESPONSE AND EVENT
################################################
def on_event_or_response(self, message):
    # print("message",message)
    pass
```

Lastly, the SDK Script overwrites the on_finish event so that whenever the function is triggered the script stops. If the user wishes to save some information recorded within the Exchange SDK this would be the opportunity to export them to external files.

```python
################################################
# SIMULATION TERMINATION CONDITION
################################################
def on_finish(self, finish_info):
    # TODO export relevant information stored during the simulation (if needed)
    self.is_finished = True
```

The rest of the script is used to connect to a running simulation/collaboration/Canary Test Network. These lines should work as is and no changes are required.

```python
################################################
# REGISTER FOR MARKETS
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
    Returns a list of the Market, Load, PV and Storage nodes the user is registered to
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


# Code to create the market aggregator and connect to the relevant simulation. Keep it as is
if os.environ["API_CLIENT_RUN_ON_REDIS"] == "true":
    MarketClient = RedisMarketClient
    market_args = {"autoregister": True}
    aggr = Oracle(aggregator_name=oracle_name)

else:
    MarketClient = RestMarketClient
    simulation_id = os.environ["API_CLIENT_SIMULATION_ID"]
    domain_name = os.environ["API_CLIENT_DOMAIN_NAME"]
    websockets_domain_name = os.environ["API_CLIENT_WEBSOCKET_DOMAIN_NAME"]
    market_args = {"simulation_id": simulation_id,
                   "domain_name": domain_name, "websockets_domain_name": websockets_domain_name}

    aggr = Oracle(aggregator_name=oracle_name, **market_args)
    if automatic:
        registry = aggr.get_configuration_registry()
        market_names = get_assets_name(registry)["Area"]

market_prices, planned_fee = fee_strategy()

print()
print('Connecting to markets ...')

for i in market_names:
    if os.environ["API_CLIENT_RUN_ON_REDIS"] == "true":
        market_registered = RedisMarketClient(area_id=i)
    else:
        market_uuid = get_area_uuid_from_area_name_and_collaboration_id(market_args["simulation_id"], i, market_args["domain_name"])
        market_args["area_id"] = market_uuid
        market_registered = RestMarketClient(**market_args)
    selected = market_registered.select_aggregator(aggr.aggregator_uuid)
    print("----> Connected to ", i)
    sleep(0.3)

print(aggr.device_uuid_list)

# loop to allow persistence
while not aggr.is_finished:
    sleep(0.5)
```

For a video tutorial on the Grid Operator API, please follow this [link](https://www.youtube.com/embed/LoYoyIy-C7M).

<iframe width="560" height="315" src="https://www.youtube.com/embed/LoYoyIy-C7M" frameborder="0" allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>

*The next step is to adapt the [Grid Operator API template script](https://github.com/gridsingularity/gsy-e-sdk/blob/master/gsy_e_sdk/setups/grid_operator_api_template.py)) developed by Grid Singularity to customize the grid fee strategies as you wish!*
