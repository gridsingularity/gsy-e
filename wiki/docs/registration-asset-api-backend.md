*Note: If you are running the Grid Singularity exchange (previously callled D3A) using a virtual machine and [vagrant](vm-installation-instructions.md), the latest GSy-e SDK is already installed on your computer and you can skip to the Launch Simulation section below. If you are running the exchange software locally, please follow the following instructions.*

###Start Redis server

To use the API locally, your script interacts with the simulation using a local Redis instance. To start the redis instance, open a new terminal and run the following command :

```
redis-server /usr/local/etc/redis.conf
```

To install redis in Ubuntu follow the instructions in this [link](https://redis.io/topics/quickstart){target=_blank}.


###Open external connection to API for Assets

In the setup file (template available [here](https://github.com/gridsingularity/gsy-e/blob/master/src/gsy_e/setup/api_setup/default_community.py){target=_blank}), an asset must be designated as open to external connection via the API. This is controlled when setting up the simulation in the setup file by designating the ExternalStrategy for each relevant energy assets :

```
Market('Family 3 children+PV+Batt',
                         [
                             Asset('Load 3 L17', strategy=LoadProfileExternalStrategy(
                                 daily_load_profile=os.path.join(current_dir,
                                                                 "resources/CHR41 Family with 3 children, both at work HH1.csv"),
                                 initial_buying_rate=Load_initial_buying_rate,
                                 final_buying_rate=Load_final_buying_rate),
                                  ),
                             Asset('PV 3 (5kW)', strategy=PVUserProfileExternalStrategy(
                                 power_profile=os.path.join(current_dir, "resources/Berlin_pv.csv"),
                                 panel_count=5,
                                 initial_selling_rate=30,
                                 final_selling_rate=11),
                                  ),
                             Asset('Tesla Powerwall 3', strategy=StorageExternalStrategy(initial_soc=10,
54min_allowed_soc=10,
battery_capacity_kWh=14,
max_abs_battery_power_kW=5,
initial_buying_rate=0,
final_buying_rate=25,
initial_selling_rate=30,                                                                              final_selling_rate=25.1),
                                  ),
                         ]),

```


By default, trading strategies do not allow API connections unless the `ExternalStrategy` is used. Please also ensure that the appropriate libraries are imported to use the API.

###Launch simulation

This requires you to have the backend codebase installed on your machine to run simulations (see [Installation Instructions](linux-installation-instructions.md)). First, navigate to the Grid Singularity folder (gsy) in a new terminal, then activate the Grid Singularity (gsy-env) environment with the command:
```
workon gsy-env
```

An template setup is already available in github and ready to be run [here](https://github.com/gridsingularity/gsy-e/blob/master/src/gsy_e/setup/api_setup/default_community.py){target=_blank} (data available for the July 2021).

To run this simulation and wait for the API template script to execute:

```
gsy-env -l INFO run -t 15s -s 15m --setup api_setup.default_community --slot-length-realtime 5 --start-date 2021-07-01 --enable-external-connection --paused
```

After few seconds, the simulation should begin, waiting for the API template as mentioned in the figure below:

![alt_text](img/api-overview-2.png)

[Here](setup-configuration.md) you can find more information on launching a simulation on the backend.

##Initialise and start the API :

Before launching the SDK Script, users need to adapt the following information in their script:

###Oracle name

This parameter is only relevant when using the API on the User-Interface. This defines the name of the aggregator / API name that manages the markets and energy assets. Once the name is set it cannot be changed within the same running collaboration.

```
oracle_name = 'oracle'
```


###Assets list

The list of assets  needs to be updated to include the assets registered to user through the registration process, in arrays as follows :

```
load_names = ['Load 1 L13', 'Load 2 L21', 'Load 3 L17']
pv_names = ['PV 1 (4kW)', 'PV 3 (5kW)']
storage_names = ['Tesla Powerwall 3']
```

```
market_names = ["Grid", "Community"]
```

The SDK Script has an “automatic” connection process to manage energy assets. If the function *automatic* is True, the Exchange SDK will automatically connect to all energy assets that it is registered to. This option is only available for simulations running on the User-Interface.

###Interact with local simulations

To interact with a locally running simulation (backend simulation), username, passwords, domain and websocket names and simulation_id are not necessary. There is only an additional flag required in the CLI command : --run-on-redis.

```
gsy-e-sdk --log-level INFO run --setup asset_api_template --run-on-redis
```

####Log levels:

The API CLI command can receive a _--log-level_ argument. Adjusting this parameter will increase or reduce the level of information displayed in the terminal, while the agent is running. There are 4 levels (classed from low detailed to high:


#####ERROR

Display only critical errors from the Exchange SDK or the Grid Singularity Exchange (for instance, if Grid Singularity Exchange responds with an error in a command that the Exchange SDK is sending, the error log should include it)

#####WARNING

Display non-critical error messages  (for instance if the API agent is over bidding its energy requirement)

#####INFO

Display critical and non-critical errors messages and general information such as market progression and trades

#####DEBUG

Display full information on the agent (for instance all command and response, such as placing bids and offers on the market)

For a video tutorial on the Asset API, please follow this [link](https://youtu.be/oCcQ6pYFd5w){target=_blank}.

*We recommend that the users experiment with trading strategies, verify their data and familiarize themselves with the Grid Singularity user interface and APIs in a Collaboration environment before initiating a Canary Test Network.*
