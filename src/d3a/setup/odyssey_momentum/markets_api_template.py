# flake8: noqa

"""
Template file for markets management through the d3a API client
"""
import pandas as pd
import logging
import os
from time import sleep
from d3a_api_client.redis_aggregator import RedisAggregator
from d3a_api_client.redis_market import RedisMarketClient
from pendulum import from_format
from d3a_interface.constants_limits import DATE_TIME_FORMAT, TIME_FORMAT
from d3a_interface.utils import key_in_dict_and_not_none
from d3a_api_client.aggregator import Aggregator
from d3a_api_client.utils import get_area_uuid_from_area_name_and_collaboration_id
from d3a_api_client.rest_market import RestMarketClient
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.disabled = True  # set to False to see all the logs
TIME_ZONE = "UTC"

# List of market the Grid Operators connect to
market_names = ["Grid", "Community"]

# Name of your aggregator
aggregator_name = "my_aggregator_name"

# Grid tariff selection
TimeOfUse = True  # Activate the Time of Use model if set to True
Aziiz = False  # Activate the Aziiz model if set to True
moving_average_peak = True  # perform a moving average of the last #look_back ptu (for the Aziiz tariff only)
look_back = 4  # number of past markets slots to apply the moving average (for the Aziiz tariff only)


# Login information of the Grid Operator (needed for UI connection)
os.environ["API_CLIENT_USERNAME"] = "Username"
os.environ["API_CLIENT_PASSWORD"] = "Password"

RUN_ON_D3A_WEB = False  # TODO set to true if joining collaboration through UI, false if running simulation locally
simulation_id = 'UUID_of_the_simulation'  # TODO update simulation id with experiment id (if RUN_ON_D3A_WEB is TRUE)
domain_name = 'https://d3aweb.gridsingularity.com'  # leave as is
websocket_domain_name = 'wss://d3aweb.gridsingularity.com/external-ws'  # leave as is


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
        self.balance_hist = pd.DataFrame(columns=market_names)

    def change_fee_print(self, area_name):
        try:
            self.next_fee = round(self.next_fee, 2)
            print(f"{area_name} changed grid fee from {self.current_market_fee[area_name]} to {self.next_fee}")
        except :
            print(f"{area_name} grid fee format is not good")

    def ToU (self):
    ###################################################################
    # DEFINE TIME OF USE STRATEGY
    ###################################################################
    # This strategy will set grid fee for a specific market for a specific time and day.
    # This strategy will only be activate if "TimeOfUse" is set to True
    # The structure is : planed_fee.update({('PUT TIME HERE','PUT MARKET NAME HERE'): PUT GRID FEE VALUE in cts/kWh })
        planed_fee = {('00:00', 'Grid'): 1.68}
        planed_fee.update({('00:00', 'Community'): 0.42})
        planed_fee.update({('00:15', 'Grid'): 1.68})
        planed_fee.update({('00:15', 'Community'): 0.42})
        planed_fee.update({('00:30', 'Grid'): 1.84})
        planed_fee.update({('00:30', 'Community'): 0.46})
        planed_fee.update({('00:45', 'Grid'): 1.76})
        planed_fee.update({('00:45', 'Community'): 0.44})
        planed_fee.update({('01:00', 'Grid'): 1.76})
        planed_fee.update({('01:00', 'Community'): 0.44})
        planed_fee.update({('01:15', 'Grid'): 1.76})
        planed_fee.update({('01:15', 'Community'): 0.44})
        planed_fee.update({('01:30', 'Grid'): 1.76})
        planed_fee.update({('01:30', 'Community'): 0.44})
        planed_fee.update({('01:45', 'Grid'): 1.76})
        planed_fee.update({('01:45', 'Community'): 0.44})
        planed_fee.update({('02:00', 'Grid'): 1.92})
        planed_fee.update({('02:00', 'Community'): 0.48})
        planed_fee.update({('02:15', 'Grid'): 2})
        planed_fee.update({('02:15', 'Community'): 0.5})
        planed_fee.update({('02:30', 'Grid'): 2.08})
        planed_fee.update({('02:30', 'Community'): 0.52})
        planed_fee.update({('02:45', 'Grid'): 2.16})
        planed_fee.update({('02:45', 'Community'): 0.54})
        planed_fee.update({('03:00', 'Grid'): 2.08})
        planed_fee.update({('03:00', 'Community'): 0.52})
        planed_fee.update({('03:15', 'Grid'): 2})
        planed_fee.update({('03:15', 'Community'): 0.5})
        planed_fee.update({('03:30', 'Grid'): 2.08})
        planed_fee.update({('03:30', 'Community'): 0.52})
        planed_fee.update({('03:45', 'Grid'): 1.92})
        planed_fee.update({('03:45', 'Community'): 0.48})
        planed_fee.update({('04:00', 'Grid'): 2})
        planed_fee.update({('04:00', 'Community'): 0.5})
        planed_fee.update({('04:15', 'Grid'): 2})
        planed_fee.update({('04:15', 'Community'): 0.5})
        planed_fee.update({('04:30', 'Grid'): 2})
        planed_fee.update({('04:30', 'Community'): 0.5})
        planed_fee.update({('04:45', 'Grid'): 2.16})
        planed_fee.update({('04:45', 'Community'): 0.54})
        planed_fee.update({('05:00', 'Grid'): 2.32})
        planed_fee.update({('05:00', 'Community'): 0.58})
        planed_fee.update({('05:15', 'Grid'): 2.4})
        planed_fee.update({('05:15', 'Community'): 0.6})
        planed_fee.update({('05:30', 'Grid'): 2.4})
        planed_fee.update({('05:30', 'Community'): 0.6})
        planed_fee.update({('05:45', 'Grid'): 2.32})
        planed_fee.update({('05:45', 'Community'): 0.58})
        planed_fee.update({('06:00', 'Grid'): 2.32})
        planed_fee.update({('06:00', 'Community'): 0.58})
        planed_fee.update({('06:15', 'Grid'): 2.4})
        planed_fee.update({('06:15', 'Community'): 0.6})
        planed_fee.update({('06:30', 'Grid'): 2.32})
        planed_fee.update({('06:30', 'Community'): 0.58})
        planed_fee.update({('06:45', 'Grid'): 2.32})
        planed_fee.update({('06:45', 'Community'): 0.58})
        planed_fee.update({('07:00', 'Grid'): 2.32})
        planed_fee.update({('07:00', 'Community'): 0.58})
        planed_fee.update({('07:15', 'Grid'): 2.72})
        planed_fee.update({('07:15', 'Community'): 0.68})
        planed_fee.update({('07:30', 'Grid'): 3.28})
        planed_fee.update({('07:30', 'Community'): 0.82})
        planed_fee.update({('07:45', 'Grid'): 3.6})
        planed_fee.update({('07:45', 'Community'): 0.9})
        planed_fee.update({('08:00', 'Grid'): 3.84})
        planed_fee.update({('08:00', 'Community'): 0.96})
        planed_fee.update({('08:15', 'Grid'): 3.52})
        planed_fee.update({('08:15', 'Community'): 0.88})
        planed_fee.update({('08:30', 'Grid'): 3.2})
        planed_fee.update({('08:30', 'Community'): 0.8})
        planed_fee.update({('08:45', 'Grid'): 2.96})
        planed_fee.update({('08:45', 'Community'): 0.74})
        planed_fee.update({('09:00', 'Grid'): 2.8})
        planed_fee.update({('09:00', 'Community'): 0.7})
        planed_fee.update({('09:15', 'Grid'): 2.72})
        planed_fee.update({('09:15', 'Community'): 0.68})
        planed_fee.update({('09:30', 'Grid'): 2.8})
        planed_fee.update({('09:30', 'Community'): 0.7})
        planed_fee.update({('09:45', 'Grid'): 3.04})
        planed_fee.update({('09:45', 'Community'): 0.76})
        planed_fee.update({('10:00', 'Grid'): 3.52})
        planed_fee.update({('10:00', 'Community'): 0.88})
        planed_fee.update({('10:15', 'Grid'): 4.16})
        planed_fee.update({('10:15', 'Community'): 1.04})
        planed_fee.update({('10:30', 'Grid'): 4.72})
        planed_fee.update({('10:30', 'Community'): 1.18})
        planed_fee.update({('10:45', 'Grid'): 5.12})
        planed_fee.update({('10:45', 'Community'): 1.28})
        planed_fee.update({('11:00', 'Grid'): 5.28})
        planed_fee.update({('11:00', 'Community'): 1.32})
        planed_fee.update({('11:15', 'Grid'): 5.2})
        planed_fee.update({('11:15', 'Community'): 1.3})
        planed_fee.update({('11:30', 'Grid'): 5.12})
        planed_fee.update({('11:30', 'Community'): 1.28})
        planed_fee.update({('11:45', 'Grid'): 5.2})
        planed_fee.update({('11:45', 'Community'): 1.3})
        planed_fee.update({('12:00', 'Grid'): 5.44})
        planed_fee.update({('12:00', 'Community'): 1.36})
        planed_fee.update({('12:15', 'Grid'): 5.6})
        planed_fee.update({('12:15', 'Community'): 1.4})
        planed_fee.update({('12:30', 'Grid'): 6.08})
        planed_fee.update({('12:30', 'Community'): 1.52})
        planed_fee.update({('12:45', 'Grid'): 6.32})
        planed_fee.update({('12:45', 'Community'): 1.58})
        planed_fee.update({('13:00', 'Grid'): 6.48})
        planed_fee.update({('13:00', 'Community'): 1.62})
        planed_fee.update({('13:15', 'Grid'): 6.56})
        planed_fee.update({('13:15', 'Community'): 1.64})
        planed_fee.update({('13:30', 'Grid'): 6.16})
        planed_fee.update({('13:30', 'Community'): 1.54})
        planed_fee.update({('13:45', 'Grid'): 5.84})
        planed_fee.update({('13:45', 'Community'): 1.46})
        planed_fee.update({('14:00', 'Grid'): 5.44})
        planed_fee.update({('14:00', 'Community'): 1.36})
        planed_fee.update({('14:15', 'Grid'): 5.04})
        planed_fee.update({('14:15', 'Community'): 1.26})
        planed_fee.update({('14:30', 'Grid'): 4.48})
        planed_fee.update({('14:30', 'Community'): 1.12})
        planed_fee.update({('14:45', 'Grid'): 3.68})
        planed_fee.update({('14:45', 'Community'): 0.92})
        planed_fee.update({('15:00', 'Grid'): 2.88})
        planed_fee.update({('15:00', 'Community'): 0.72})
        planed_fee.update({('15:15', 'Grid'): 2})
        planed_fee.update({('15:15', 'Community'): 0.5})
        planed_fee.update({('15:30', 'Grid'): 1.6})
        planed_fee.update({('15:30', 'Community'): 0.4})
        planed_fee.update({('15:45', 'Grid'): 1.52})
        planed_fee.update({('15:45', 'Community'): 0.38})
        planed_fee.update({('16:00', 'Grid'): 1.68})
        planed_fee.update({('16:00', 'Community'): 0.42})
        planed_fee.update({('16:15', 'Grid'): 2.08})
        planed_fee.update({('16:15', 'Community'): 0.52})
        planed_fee.update({('16:30', 'Grid'): 2.32})
        planed_fee.update({('16:30', 'Community'): 0.58})
        planed_fee.update({('16:45', 'Grid'): 2.64})
        planed_fee.update({('16:45', 'Community'): 0.66})
        planed_fee.update({('17:00', 'Grid'): 2.88})
        planed_fee.update({('17:00', 'Community'): 0.72})
        planed_fee.update({('17:15', 'Grid'): 3.2})
        planed_fee.update({('17:15', 'Community'): 0.8})
        planed_fee.update({('17:30', 'Grid'): 3.6})
        planed_fee.update({('17:30', 'Community'): 0.9})
        planed_fee.update({('17:45', 'Grid'): 3.92})
        planed_fee.update({('17:45', 'Community'): 0.98})
        planed_fee.update({('18:00', 'Grid'): 4.08})
        planed_fee.update({('18:00', 'Community'): 1.02})
        planed_fee.update({('18:15', 'Grid'): 4.4})
        planed_fee.update({('18:15', 'Community'): 1.1})
        planed_fee.update({('18:30', 'Grid'): 4.56})
        planed_fee.update({('18:30', 'Community'): 1.14})
        planed_fee.update({('18:45', 'Grid'): 4.72})
        planed_fee.update({('18:45', 'Community'): 1.18})
        planed_fee.update({('19:00', 'Grid'): 4.8})
        planed_fee.update({('19:00', 'Community'): 1.2})
        planed_fee.update({('19:15', 'Grid'): 4.64})
        planed_fee.update({('19:15', 'Community'): 1.16})
        planed_fee.update({('19:30', 'Grid'): 4.56})
        planed_fee.update({('19:30', 'Community'): 1.14})
        planed_fee.update({('19:45', 'Grid'): 4.24})
        planed_fee.update({('19:45', 'Community'): 1.06})
        planed_fee.update({('20:00', 'Grid'): 3.92})
        planed_fee.update({('20:00', 'Community'): 0.98})
        planed_fee.update({('20:15', 'Grid'): 3.52})
        planed_fee.update({('20:15', 'Community'): 0.88})
        planed_fee.update({('20:30', 'Grid'): 3.12})
        planed_fee.update({('20:30', 'Community'): 0.78})
        planed_fee.update({('20:45', 'Grid'): 2.88})
        planed_fee.update({('20:45', 'Community'): 0.72})
        planed_fee.update({('21:00', 'Grid'): 2.72})
        planed_fee.update({('21:00', 'Community'): 0.68})
        planed_fee.update({('21:15', 'Grid'): 2.64})
        planed_fee.update({('21:15', 'Community'): 0.66})
        planed_fee.update({('21:30', 'Grid'): 2.72})
        planed_fee.update({('21:30', 'Community'): 0.68})
        planed_fee.update({('21:45', 'Grid'): 2.8})
        planed_fee.update({('21:45', 'Community'): 0.7})
        planed_fee.update({('22:00', 'Grid'): 2.72})
        planed_fee.update({('22:00', 'Community'): 0.68})
        planed_fee.update({('22:15', 'Grid'): 2.72})
        planed_fee.update({('22:15', 'Community'): 0.68})
        planed_fee.update({('22:30', 'Grid'): 2.64})
        planed_fee.update({('22:30', 'Community'): 0.66})
        planed_fee.update({('22:45', 'Grid'): 2.4})
        planed_fee.update({('22:45', 'Community'): 0.6})
        planed_fee.update({('23:00', 'Grid'): 2.24})
        planed_fee.update({('23:00', 'Community'): 0.56})
        planed_fee.update({('23:15', 'Grid'): 2.16})
        planed_fee.update({('23:15', 'Community'): 0.54})
        planed_fee.update({('23:30', 'Grid'): 1.92})
        planed_fee.update({('23:30', 'Community'): 0.48})
        planed_fee.update({('23:45', 'Grid'): 1.84})
        planed_fee.update({('23:45', 'Community'): 0.46})
        return planed_fee


    def scheduled_fee(self, market_time, planned_fee, market_name):
        slot_time = market_time.add(minutes=1*slot_length).time().format(TIME_FORMAT)
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
        self.balance={}

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

        # In this loop dso_market_stats is called for every connected market and stored in self.dso_stats
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
                        try :
                            self.balance[area_event['name']] = self.import_kWh[area_event['name']]-self.export_kWh[area_event['name']]
                        except :
                            self.balance[area_event['name']] = 0

        self.balance_hist = self.balance_hist.append(self.balance, ignore_index=True)

        # Print information in the terminal
        print('LAST MARKET STATISTICS :')
        print('total energy traded:', self.total_traded_energy_kWh)
        print('trade rates: min: ', self.min_trade_rate, '// avg: ', self.avg_trade_rate, '// med: ',self.median_trade_rate, '// max: ', self.max_trade_rate)
        print("self sufficiency: ", self.self_sufficiency)
        print("Energy imported: ", self.import_kWh)
        print("Energy exported: ", self.export_kWh)
        print('last fee:', self.last_market_fee)
        print()
        print('CURRENT MARKET')
        print('current fee:', self.current_market_fee)
        print()


        # This loop is used to set the batch command for the new grid fee
        for area_event in market_info["content"]:
            if key_in_dict_and_not_none(area_event, "area_uuid") and area_event["name"] in market_names:
                area_uuid = area_event["area_uuid"]
                if area_uuid not in batch_commands:
                    batch_commands[area_uuid] = []

                # Initialize the next market fee being to equal to the current one
                self.next_fee = self.current_market_fee[area_event["name"]]


                ###################################################################
                # TIME OF USE STRATEGY
                ###################################################################
                if TimeOfUse:
                    planed_fee = self.ToU()
                    self.next_fee = self.scheduled_fee(market_time,planed_fee,area_event['name'])

                ###################################################################
                # AZIIZ STRATEGY
                ###################################################################
                if Aziiz:
                    if moving_average_peak:
                        self.max_ext_energy_kWh = abs(self.balance_hist["Community"].iloc[-look_back:].mean())  # Calculate the absolute moving average of the net balance
                    else:
                        self.max_ext_energy_kWh = max(self.import_kWh['Community'], self.export_kWh['Community'])  # Calculate the max between the import and export of the defined market
                    if area_event['name'] == "Grid":  # market name in which grid fees will be changed
                        print('Community peak : ', self.max_ext_energy_kWh)
                        if self.max_ext_energy_kWh <= 10:  # if the peak is lower than this value, the following grid fee will be applied. If the max is higher, it will go to the lower elif condition
                            self.next_fee = 0.9  # new grid fee
                        elif self.max_ext_energy_kWh <= 15:
                            self.next_fee = 2.1
                        elif self.max_ext_energy_kWh <= 20:
                            self.next_fee = 3
                        elif self.max_ext_energy_kWh <= 25:
                            self.next_fee = 3.9
                        elif self.max_ext_energy_kWh <= 30:
                            self.next_fee = 6
                        elif self.max_ext_energy_kWh <= 50:
                            self.next_fee = 30
                        else:
                            self.next_fee = 2000

                    if area_event['name'] == "Community":  # market name in which grid fees will be changed
                        if self.max_ext_energy_kWh <= 10:  # if the peak is lower than this value, the following grid fee will be applied. If the max is higher, it will go to the lower elif condition
                            self.next_fee = 0.9  # new grid fee
                        elif self.max_ext_energy_kWh <= 15:
                            self.next_fee = 2.1
                        elif self.max_ext_energy_kWh <= 20:
                            self.next_fee = 3
                        elif self.max_ext_energy_kWh <= 25:
                            self.next_fee = 3.9
                        elif self.max_ext_energy_kWh <= 30:
                            self.next_fee = 6
                        elif self.max_ext_energy_kWh <= 50:
                            self.next_fee = 30
                        else:
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
            logging.info(f"Batch command placed on the new market: {response}")
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
print(aggregator.device_uuid_list)
while not aggregator.is_finished:
    sleep(0.5)
