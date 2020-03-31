# API documentation
The D3A API client allows you to create agents that follow custom trading strategies to buy and sell energy in the energy market. The agent can request and receive information through the API, feed that information into an algorithm, and post bids or offers on a live simulated exchange. This document covers installation and descriptions of the functions available.

### API Client Installation
Note, if you are running the d3a using a virtual machine and vagrant, the latest api-client is already installed on your machine and you can skip to the `Launch Simulation` section below. If you are running the d3a locally, please follow the following instructions.

#### Install Redis server. Open a new terminal and type
``` 
brew install redis
```

#### Install d3a-client
```
mkvirtualenv d3a-api-env
pip install git+https://github.com/gridsingularity/d3a-api-client.git
```

#### Update d3a-client (as needed when an update is deployed)

```
pip uninstall d3a-api-client
pip install git+https://github.com/gridsingularity/d3a-api-client.git
```


### Using the API Client with a Running Simulation

#### Start Redis server

To use the API locally, your script connects to the simulation using a local Redis instance. To start the redis instance, open a new terminal and run the following command : 

```
redis-server /usr/local/etc/redis.conf
```

#### Launch simulation 
This requires you to have the d3a simulation installed on your machine. If you have yet to do this, see the installation instructions. First navigate to the d3a folder in a new terminal, then activate the d3a environment with:

```
workon d3a
```

Then run:
```
d3a -l INFO run -t 15s -s 15m --setup hackathon_training.HackTrain_01_simple --start-date 2016-10-06
```

Note that this uses the simpler version of the full hack file, and runs more quickly. To run the full community, run:
```
d3a -l INFO run -t 15s -s 15m --setup hackathon_training.HackTrain_01 --start-date 2016-10-06
```

After a few seconds, trading should begin, and should look something like the below.
![img](img/api-1.png)

### Launch smart agents
Open a new terminal to run your trading strategy script (python file). In this python file you can code the trading strategy for the assets you manage. A template python script is provided. You are also able to print some information that you will get with your API calls.

You can run your script in the terminal. First navigate to the folder `d3a/src/d3a/setup/hackathon_training/`

Then run
```
python agent_api_template.py
```

### Simulation speed
There are multiple factors that can impact the simulation speed and therefore your training time. 

**First the number of Areas/Devices**: The more Areas/Devices that you have in your simulation the longer it will take to finish. (Warning: the correlation between the number of nodes and the simulation speed is not linear, but exponential!)

**Secondly this variable: ConstSettings.GeneralSettings.DEFAULT_UPDATE_INTERVAL**

By decreasing the latter’s value, template agents will update their bids/offers more frequently and therefore the simulation will take more time to finish.

**Third, your python interpreter:**

To significantly increase the simulation speed you can also change your interpreter. Instead of using the default interpreter “Cpython”, you can use “pypy” which is much faster for repetitive tasks. Here are the steps to use pypy with the d3a:

#### 1. Install pypy3
```	
Brew install pypy3
```

#### 2. Create a virtual environment using pypy3

```
mkvirtualenv -p [path_to_pypy3] env_name
```
#### 3. Work in your new virtual environment
```
workon env_name
```
#### 4. Install fabric3
```
pip install fabric3
```
Go to d3a folder `cd d3a`

#### 5. Install all dependencies
```
pip install -e .
```

You’re all set to launch simulations from this virtual environment. 

### Grid Setup File Configuration

Backend simulations require modifications to the setup files to allow API connections. When you connect to the web application, the grid operator will make the necessary changes instead. This section is only relevant if you’re modifying your own setup files.

#### Open Device for external connection
In the setup file, a device must be designated as open to external connection via the API. This is controlled when setting up the simulation in the setup file by designating the ExternalStrategy for each relevant device: 
```python
Area( 'house-1-s',
              [
                     Area('h1-load-s', strategy=LoadProfileExternalStrategy(daily_load_profile=load1,
                                                                             initial_buying_rate=Houses_initial_buying_rate,
                                                                             use_market_maker_rate=True),
                     appliance=SwitchableAppliance()),

                     Area('h1-pv-s', strategy=PVUserProfileExternalStrategy(power_profile=pv1,
                                                                             initial_selling_rate=PV_initial,
                                                                             final_selling_rate=PV_final),
                     appliance=PVAppliance()),
                   
                     Area('h1-storage-s', strategy=StorageExternalStrategy(initial_soc=50),
                     appliance=SwitchableAppliance()),
                 
               ], grid_fee_percentage=0, transfer_fee_const=0, external_connection_available=True
           ),
```
By default, template strategies do not allow connections. Please also ensure that the appropriate libraries are imported (as in the template setup file provided).

#### Open Area for external connection
The API supports multiple areas exposing their market statistics (e.g. min, max, avg, median price and volume of energy) to external devices. Access is controlled when setting up the simulation, using the Area class boolean argument called external_connection_available: 
```python
Area(
         'House 2',
         [ ... ], # Children of the area
         external_connection_available=True
),
```
If set to true, the area allows all of its ‘child’ devices to request its market statistics. By default, this external_connection_available is set to False.


### API Commands
There are multiple instances that can get you information or enable you to take action in the simulation.

#### Event-Triggered Functions
In order to facilitate offer and bid management and scheduling, a python file with the class AutoDeviceStrategy is provided, where four functions which are triggered on different types of events can be overridden, useful to take actions when market events occur.

##### Each New Market Slot (on_market_cycle(self, market_info))
When a new market slot is available the client will get notified via an event. It is possible to capture this event and perform operations after it by overriding the on_market_cycle method.

Ex: `def on_market_cycle(self, market_info):`

In the variable market_info you will get a dictionary with information on the market and your devices. The return values are the following : 
```json
{
  "name": "house2", 
  "id": "13023c7d-205d-4b3a-a434-02375eb277ca", 
  "start_time": start-time of the market slot, 
  "duration_min": 15, 
  "device_info": {
    "energy_requirement_kWh": energy that the device has to buy during this market slot, 
    "available_energy_kWh": energy that the device has to sell during this market slot
  }, 
  "event": "market", 
  "device_bill": {
    "bought": energy bought in kWh, 
    "sold": energy sold in kWh, 
    "spent": money spent in €, 
    "earned": money earned in €, 
    "total_energy": bought - sold, 
    "total_cost": spent - earned, 
    "market_fee": € that goes in grid fee, 
    "type": type of the strategy
    }, 
  "last_market_stats": {
    "min_trade_rate": minimum trade price in €/kWh, 
    "max_trade_rate": maximum trade price in €/kWh, 
    "avg_trade_rate": average trade price in €/kWh, 
    "total_traded_energy_kWh": total energy traded in kWh
    }
}
```

##### On % of Market Slot Completion (on_tick(self, tick_info))

Each 10% of market slot completion (e.g. 10%, 20%, 30%, …), the same information as market_info will be passed, updated with new device energy requirements. This can be used to update your bid or offer price at these milestones.

##### On Trade (on_trade(self, trade_info))

Each time the device you manage makes a trade, information about the trade is passed through trade_info. This information can be stored locally or acted upon.

##### On Simulation Finish (on_finished(self))

This executes when the simulation finishes, and can be used to trigger exporting data, training a model or exiting the code.

### Device Commands
#### Register - Backend
Each team will have to register to devices in order to implement their strategies.  Let’s take this area excerpt from the setup file as an example:
```python
Area(
                'house2',
                [
                    Area('load2', strategy=LoadHoursExternalStrategy(avg_power_W=200,
                                             hrs_per_day=20,
                                             hrs_of_day=list(
                                             range(2, 22)),
                                            final_buying_rate=35, initial_buying_rate=0),
                         appliance=SwitchableAppliance()),
                                   ],
                grid_fee_percentage=0, transfer_fee_const=0, external_connection_available=True
            ),
```

Here we will take control of the area “load2”. There are 2 ways to register for this device: 

1. The constructor of the API class can connect and register automatically to a running simulation:
```
r = RedisDeviceClient('load2', autoregister=True)
```
2. You can also do it manually :
```
r = RedisDeviceClient('load2', autoregister=False)
r.register()
```

To disconnect/unregister from a simulation, the following command is available:
```
r.unregister()
```
#### Register - Frontend
To register for a collaboration (public simulation hosted by a grid operator) on d3a.io, limited changes must be made in the agent script. This information will be available before the first test on d3a.io.

##### Send an energy offer (offer_energy(energy[kWh], price[€]))

PVs and batteries can offer energy.

Ex: `r.offer_energy(3, 0.8)`

##### Send an energy bid (bid_energy(energy[kWh], price[€]))

Loads, batteries, and flexible loads can bid for energy.

Ex: `r.bid_energy(2, 3)`

##### Lists all posted offers

Ex: `r.list_offers()`

##### Lists all posted bids

Ex: `r.list_bids()`

##### Delete offer using its ID (delete_offer(id=None))

With no argument, delete all active offers. With ID as argument, delete only offer with set ID

Ex: `r.delete_offer('1d352704-d787-4aa1-b1ad-dc10e22b2fc2')`

##### Delete bid using its ID (delete_bid(id=None))

With no argument, delete all active bids. With ID as argument, delete only bid with set ID

Ex: `r.delete_bid('1d352704-d787-4aa1-b1ad-dc10e22b2fc2')`

Note: The total amount of energy bid at any point is limited to the energy requirement of the device. If you want to update a bid during a market slot, you must delete the specific bid and post a new one.



