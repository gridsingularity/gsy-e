# flake8: noqa

"""
Template file for markets management through the d3a API client
"""

import logging
import os
from time import sleep
from d3a_api_client.redis_aggregator import RedisAggregator
from d3a_api_client.redis_market import RedisMarketClient
from pendulum import from_format
from d3a_interface.constants_limits import DATE_TIME_FORMAT
from d3a_interface.utils import key_in_dict_and_not_none
from d3a_api_client.aggregator import Aggregator
from d3a_api_client.utils import get_area_uuid_from_area_name_and_collaboration_id
from d3a_api_client.rest_market import RestMarketClient
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.disabled = True # set to False to see all the logs
TIME_ZONE = "UTC"

# List of market the Grid Operators connect to
market_names = ["Grid", "Community"]

# Name of your aggregator
aggregator_name = "Aggregator_name"

# Login information of the Grid Operator
os.environ["API_CLIENT_USERNAME"] = "user_name"
os.environ["API_CLIENT_PASSWORD"] = "password"

RUN_ON_D3A_WEB = False # TODO set to true if joining collaboration through UI, false if running simulation locally
simulation_id = 'UUID of the simulation' # TODO update simulation id with experiment id (if RUN_ON_D3A_WEB is TRUE)
domain_name = 'https://d3aweb.gridsingularity.com' # leave as is
websocket_domain_name = 'wss://d3aweb.gridsingularity.com/external-ws' # leave as is

if RUN_ON_D3A_WEB:
    Aggregator_type = Aggregator
else:
    Aggregator_type = RedisAggregator

slot_length = 15 # leave as is

class AutoAggregator(Aggregator_type):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_finished = False
        self.next_fee = None

    def change_fee_print(self, area_name):
        try:
            self.next_fee = round(self.next_fee, 2)
            print(f"{area_name} changed grid fee from {self.current_market_fee[area_name]} to {self.next_fee}")
        except :
            print(f"{area_name} grid fee format is not good")

    def scheduled_fee(self, market_time, planned_fee, market_name):
        slot_time = market_time.add(minutes=1*slot_length).format(DATE_TIME_FORMAT)

        if (slot_time, market_name) in planned_fee:
            next_fee = planned_fee[(slot_time, market_name)]
        else:
            next_fee = None
        return next_fee

    # This function is triggered at the end of each market slot. It is in this function that information can be called and grid fee algorithm can be designed
    def on_market_cycle(self, market_info):

        # Initialization of variables
        self.last_market_fee={}
        self.current_market_fee={}
        self.min_trade_rate={}
        self.avg_trade_rate={}
        self.max_trade_rate={}
        self.median_trade_rate={}
        self.total_traded_energy_kWh={}
        self.self_sufficiency={}
        self.import_kWh={}
        self.export_kWh={}

        # Print market time
        for area_event in market_info["content"]:
            if key_in_dict_and_not_none(area_event, "area_uuid"):
                market_time = from_format(area_event['start_time'], DATE_TIME_FORMAT, tz=TIME_ZONE)
                break
        print("============================================")
        print("Market", market_time)

        # Initialize the batch command
        batch_commands = {}  # batch_command for sending new grid fee
        batch_commands_stats = {}  # batch_command for requesting market data

        # In this dso_market_stats is called for every connected market and stored in self.dso_stats
        for area_event in market_info["content"]:
            if key_in_dict_and_not_none(area_event, "area_uuid") and area_event["name"] in market_names:
                market_slot = [market_time.subtract(minutes=1*slot_length).format(DATE_TIME_FORMAT)]
                area_uuid = area_event["area_uuid"]
                if area_uuid not in batch_commands_stats:
                    batch_commands_stats[area_uuid] = []
                batch_commands_stats[area_uuid].append({"type": "dso_market_stats", "data": {"market_slots": market_slot}})

        self.dso_stats = self.batch_command(batch_commands_stats)["responses"]

        for area_event in market_info["content"]:
            # Store data in from market info into variables
            if key_in_dict_and_not_none(area_event, "area_uuid") and area_event["name"] in market_names:
                self.last_market_fee[area_event["name"]] = area_event["current_market_fee"]
                self.current_market_fee[area_event["name"]] = area_event["next_market_fee"]
                self.min_trade_rate[area_event['name']] = area_event['last_market_stats']['min_trade_rate']
                self.avg_trade_rate[area_event['name']] = area_event['last_market_stats']['avg_trade_rate']
                self.max_trade_rate[area_event['name']] = area_event['last_market_stats']['max_trade_rate']
                self.median_trade_rate[area_event['name']] = area_event['last_market_stats']['median_trade_rate']
                self.total_traded_energy_kWh[area_event['name']] = area_event['last_market_stats']['total_traded_energy_kWh']
                self.self_sufficiency[area_event['name']] = area_event['self_sufficiency']

                for area_dso in self.dso_stats:
                    if area_dso[0]["area_uuid"]==area_event["area_uuid"]:
                        self.import_kWh[area_event['name']] = area_dso[0]['market_stats'][market_time.subtract(minutes=1*slot_length).format(DATE_TIME_FORMAT)]['area_throughput']['import']
                        self.export_kWh[area_event['name']] = area_dso[0]['market_stats'][market_time.subtract(minutes=1*slot_length).format(DATE_TIME_FORMAT)]['area_throughput']['export']

        # Print information in the terminal
        print('total energy traded:', self.total_traded_energy_kWh)
        print('trade rates: min: ', self.min_trade_rate, '// avg: ', self.avg_trade_rate, '// med: ',self.median_trade_rate, '// max: ', self.max_trade_rate)
        print("self sufficiency: ", self.self_sufficiency)
        print("Energy imported: ", self.import_kWh)
        print("Energy exported: ", self.export_kWh)
        print('last fee:', self.last_market_fee)
        print('current fee:', self.current_market_fee)

        ###################################################################
        # DEFINE SCHEDULED FEE STRATEGY - TIME OF USE
        ###################################################################
        # This strategy will set grid fee for a specific market for a specific time.
        # This strategy will only be activate if "scheduled_grid_fee" is set to True
        # The structure is : planed_fee.update({('PUT DATE HERE','PUT MARKET NAME HERE'): PUT GRID FEE VALUE in cts/kWh })
        planed_fee = {('2014-10-31T00:30','Grid'): 1}
        planed_fee.update({('2014-10-31T02:00','Community'): 2})
        planed_fee.update({('2014-10-31T03:00','Grid'): 4})
        planed_fee.update({('2014-10-31T03:00','Community'): 2})
        planed_fee.update({('2014-10-31T04:00','Grid'): 5})
        planed_fee.update({('2014-10-31T04:00','Community'): 2})
        planed_fee.update({('2014-10-31T05:00','Grid'): 6})
        planed_fee.update({('2014-10-31T05:00','Community'): 1})
        planed_fee.update({('2014-10-31T06:00','Grid'): 7})
        planed_fee.update({('2014-10-31T06:00','Community'): 1})
        planed_fee.update({('2014-10-31T07:00','Grid'): 8})
        planed_fee.update({('2014-10-31T07:00','Community'): 1})
        planed_fee.update({('2014-10-31T08:00','Grid'): 6})
        planed_fee.update({('2014-10-31T08:00','Community'): 1})
        planed_fee.update({('2014-10-31T09:00','Grid'): 4})
        planed_fee.update({('2014-10-31T09:00','Community'): 1})
        planed_fee.update({('2014-10-31T10:00','Grid'): 2})
        planed_fee.update({('2014-10-31T10:00','Community'): 1})
        planed_fee.update({('2014-10-31T11:00','Grid'): 100})
        planed_fee.update({('2014-10-31T11:00','Community'): 200})

        # this loop is used to set the batch command for the new grid fee
        for area_event in market_info["content"]:
            if key_in_dict_and_not_none(area_event, "area_uuid") and area_event["name"] in market_names:
                area_uuid = area_event["area_uuid"]
                if area_uuid not in batch_commands:
                    batch_commands[area_uuid] = []

                # Initialize the next market fee being to equal to the last one
                self.next_fee = self.current_market_fee[area_event["name"]]

                # Activate the scheduled grid fee if set to True
                scheduled_grid_fee = True
                if scheduled_grid_fee:
                    self.next_fee = self.scheduled_fee(market_time,planed_fee,area_event['name'])

                ###################################################################
                # DEFINE DYNAMIC FEE STRATEGY - AZIZ STRATEGY
                ###################################################################
                # Activate the scheduled grid fee if set to True
                dynamic_fees = False
                # Fee logic reflected in if/elif statement below
                if dynamic_fees :
                    if area_event['name'] == "Grid": # market name in which grid fees will be changed
                        self.max_ext_energy_kWh = max(self.import_kWh['Community'],self.export_kWh['Community']) # Calculate the max between the import and export of the defined market
                        if self.max_ext_energy_kWh <= 6: # if the peak is lower than this value, the following grid fee will be applied. If the max is higher, it will go to the lower elif condition
                            self.next_fee = 1.5 # new grid fee
                        elif self.max_ext_energy_kWh <= 8:
                            self.next_fee = 3.5
                        elif self.max_ext_energy_kWh <= 10:
                            self.next_fee = 4
                        elif self.max_ext_energy_kWh <= 12:
                            self.next_fee = 5
                        elif self.max_ext_energy_kWh <= 14:
                            self.next_fee = 6.5
                        elif self.max_ext_energy_kWh <= 16:
                            self.next_fee = 10
                        elif self.max_ext_energy_kWh <= 18:
                            self.next_fee = 21.5
                        elif self.max_ext_energy_kWh <= 20:
                            self.next_fee = 70
                        else :
                            self.next_fee = 2000

                # Print the grid fee changes in the terminal
                if self.next_fee is not None and self.next_fee != self.current_market_fee[area_event["name"]]:
                    self.change_fee_print(area_event["name"])
                else:
                    self.next_fee = self.current_market_fee[area_event["name"]]
                    print(area_event["name"], " : grid fee remained the same")

                batch_commands[area_uuid].append({"type": "grid_fees",
                                                  "data": {"fee_const": self.next_fee}})

        # send batch command
        if batch_commands:
            response = self.batch_command(batch_commands)
            logging.warning(f"Batch command placed on the new market: {response}")
        logging.info(f"---------------------------")

## This function is triggered when the simulation has ended
    def on_finish(self, finish_info):
        self.is_finished = True
        logging.info(f"AGGREGATOR_FINISH_INFO: {finish_info}")

    def on_batch_response(self, market_stats):
        logging.info(f"AGGREGATORS_BATCH_RESPONSE: {market_stats}")

## Code to create the market aggregator and connect to the relevant simulation
if RUN_ON_D3A_WEB:
    aggregator = AutoAggregator(
        simulation_id=simulation_id,
        domain_name=domain_name,
        aggregator_name=aggregator_name,
        websockets_domain_name=websocket_domain_name
    )

    market_args = {
        "simulation_id": simulation_id,
        "domain_name": domain_name,
        "websockets_domain_name": websocket_domain_name
    }
else:
    aggregator = AutoAggregator(
        aggregator_name=aggregator_name
    )

print()
print('Connecting to markets ...')

for i in market_names:
    if RUN_ON_D3A_WEB:
        market_registered_uuid = get_area_uuid_from_area_name_and_collaboration_id(
            market_args["simulation_id"], i, market_args["domain_name"])
        market_args["area_id"] = market_registered_uuid
        market_registered = RestMarketClient(**market_args)
    else:
        market_registered = RedisMarketClient(i)

    selected = market_registered.select_aggregator(aggregator.aggregator_uuid)
    logging.warning(f"SELECTED: {selected}")
    print("----> Connected to ", i)

while not aggregator.is_finished:
    sleep(0.5)
