# flake8: noqa

"""
Template file for a trading strategy through the d3a API client
"""

import os
import logging
from d3a_api_client.redis_device import RedisDeviceClient
from d3a_api_client.rest_device import RestDeviceClient
from d3a_api_client.aggregator import Aggregator
from d3a_api_client.redis_aggregator import RedisAggregator
from d3a_interface.utils import key_in_dict_and_not_none
from pendulum import from_format, today, now
from d3a_interface.constants_limits import DATE_TIME_FORMAT
from d3a_api_client.utils import get_area_uuid_from_area_name_and_collaboration_id
import random
import logging
logger = logging.getLogger()
logger.disabled = True
TIME_ZONE = "UTC"

################################################
# CONFIGURATIONS
################################################

os.environ["API_CLIENT_USERNAME"] = "user_name"
os.environ["API_CLIENT_PASSWORD"] = "password"


# set simulation parameters
RUN_ON_D3A_WEB = False  # TODO set to true if joining collaboration through UI, false if running simulation locally
simulation_id = 'UUID of the simulation' # TODO update simulation id with experiment id (if RUN_ON_D3A_WEB is TRUE)
domain_name = 'https://d3aweb.gridsingularity.com' # leave as is
websocket_domain_name = 'wss://d3aweb.gridsingularity.com/external-ws' # leave as is

# Designate devices and markets to manage
# TODO update each of the below according to your team's device assignments
oracle_name = 'aggregator'
load_names = ['Load 1','Load 2','Load 3','Load 4','Load 5','Load 6','Load 7','Load 8','Load 10','Load 11','Load 12',
'Load 13','Load 14','Load 15','Load 16','Load 17','Load 18','Load 19','Load 20','Load 21','Load 22','Load 23','Load 24','Load 25']
pv_names = ['PV 1','PV 2','PV 3','PV 4','PV 5','PV 7','PV 8','PV 9','PV 10','PV 11','PV 12','PV 13','PV 14','PV 16','PV 17','PV 18',
'PV 19','PV 20','PV 23','PV 24','PV 25','CHP 6','CHP 13','CHP 15','CHP 21','CHP 22']
storage_names = ['Storage 1','Storage 2','Storage 3','Storage 4','Storage 5','Storage 7','Storage 8','Storage 10','Storage 11','Storage 12','Storage 14','Storage 16','Storage 17','Storage 18',
'Storage 19','Storage 20','Storage 23','Storage 24','Storage 25']

# set trading strategy parameters
market_maker_price = 22.  # leave as is
feed_in_tariff_price = 21.9  # leave as is
# set market parameters
ticks = 10  # leave as is

if RUN_ON_D3A_WEB:
    Aggregator_type = Aggregator
else:
    Aggregator_type = RedisAggregator

################################################
# ORACLE STRUCTURE
################################################

class Oracle(Aggregator_type):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_finished = False
        self.load_strategy = []
        self.pv_strategy = []
        self.batt_sell_strategy = []
        self.batt_buy_strategy = []
        # initialise grid fee variables
        self.grid_fee = 0.
        self.grid_fee_Grid = 4.
        self.grid_fee_Community = 4.

    ################################################
    # TRIGGERS EACH MARKET CYCLE
    ################################################
    def on_market_cycle(self, market_info):
        """
        Places a bid or an offer whenever a new market is created. The amount of energy
        for the bid/offer depends on the available energy of the PV, the required
        energy of the load, or the amount of energy in the battery.
        :param market_info: Incoming message containing the newly-created market info
        :return: None
        """
        # termination conditions (leave as is)
        if self.is_finished is True:
            return
        if "content" not in market_info:
            return

        # get and print market time
        for device_event in market_info["content"]:
            if key_in_dict_and_not_none(device_event, "device_info"):
                market_time = from_format(device_event['start_time'], DATE_TIME_FORMAT, tz=TIME_ZONE)
                break
        print('========================================================================================')
        print('MARKET:', market_time)
        print('--------', '00%', '--------')

        ################################################
        # GET MARKET AND ENERGY FEATURES
        ################################################

        # extract market stats and energy through aggregator
        stats_slot = [] # track areas already extracted
        market_stats = []
        load_energy_requirements = [] # track load energy requirements
        pv_energy_availabilities = [] # track pv energy availability
        battery_charges = [] # track batteries' state of charge

        # get data from each device
        for device_event in market_info["content"]:
            if key_in_dict_and_not_none(device_event, "device_info"):
            # get device energy information
                if 'energy_requirement_kWh' in device_event['device_info']:
                    load_energy_requirements.append(device_event['device_info']['energy_requirement_kWh'])
                if 'available_energy_kWh' in device_event['device_info']:
                    pv_energy_availabilities.append(device_event['device_info']['available_energy_kWh'])
                if 'used_storage' in device_event['device_info']:
                    battery_charges.append(device_event['device_info']['used_storage'])

            # get market stats from grid tree
            if key_in_dict_and_not_none(device_event, "grid_stats_tree"):
                if device_event["grid_stats_tree"][next(iter(device_event["grid_stats_tree"]))]["last_market_slot"] not in stats_slot:
                    stats_slot.append(device_event["grid_stats_tree"][next(iter(device_event["grid_stats_tree"]))]["last_market_slot"])
                    stats = device_event["grid_stats_tree"]
                    market_stats.append(stats)
                    # extract grid fee for relevant areas
                    try:
                        self.grid_fee_Grid = stats["Grid"]["next_market_fee"]
                        self.grid_fee_Community = stats["Grid"]["children"]["Community"]["next_market_fee"]
                    except:
                        pass

        # get total grid fee
        try:
            self.grid_fee = self.grid_fee_Grid+self.grid_fee_Community
        except:
            pass

        print("Total grid fee :", self.grid_fee)

        # TODO do something with the arrays if needed:
        #   - area_uuids
        #   - market_stats
        #   - load_energy_requirements
        #   - pv_energy_availabilities
        #   - battery_charges

        ################################################
        # MAKE PRICE PREDICTIONS
        ################################################

        # TODO predict market slot prices based on extracted market data and features using `market_stats`
        # predict market slot prices
        pred_min_price = 12
        pred_avg_price = 18
        pred_med_price = 20
        pred_max_price = market_maker_price # price to get to the market maker (incl. grid fees)

        ################################################
        # SET BID AND OFFER STRATEGIES
        ################################################

        # TODO configure bidding / offer strategy for each tick
        # current strategy is a simple ramp between arbitrary values. Don't use this strategy :)
        # strategies are stored in array of length 10, which are posted in ticks 1 through 10
        # the default is that each device type you control has the same strategy
        self.load_strategy = []
        self.pv_strategy = []
        self.batt_sell_strategy = []
        self.batt_buy_strategy = []
        for i in range(0, ticks):
            if i < ticks-1:
                self.load_strategy.append(pred_min_price + (pred_max_price - pred_min_price) * (i/ticks))
                self.pv_strategy.append(pred_max_price - (pred_max_price - pred_min_price) * (i / ticks))
            else: # last tick guarantee match by bidding at market maker price / offering at feed in tariff price
                self.load_strategy.append(market_maker_price+self.grid_fee)
                self.pv_strategy.append(max(0, feed_in_tariff_price-self.grid_fee))  # must be non-negative
            self.batt_buy_strategy.append(pred_min_price + (pred_med_price - pred_min_price) * (i/ticks))
            self.batt_sell_strategy.append(pred_max_price - (pred_max_price - pred_med_price) * (i / ticks))

        ################################################
        # SET INITIAL BIDS AND OFFERS FOR MARKET SLOT
        ################################################

        # takes the first element in each devices strategy
        # TODO how would you self-balance your managed energy assets?

        batch_commands = {}
        for device_event in market_info["content"]:
            if key_in_dict_and_not_none(device_event, "area_uuid"):

                # Load Strategy
                if "energy_requirement_kWh" in device_event["device_info"] and \
                        device_event["device_info"]["energy_requirement_kWh"] > 0.0:
                    price = self.load_strategy[0] * device_event["device_info"]["energy_requirement_kWh"]
                    energy = device_event["device_info"]["energy_requirement_kWh"]
                    batch_commands[device_event["area_uuid"]] = [
                        {"type": "bid",
                         "price": price,
                         "energy": energy},
                    ]
                    uuid = device_event['area_uuid']
                    print(f'{self.device_uuid_map[uuid]} BID {round(energy, 4)} kWh 'f'at {round(price / energy, 2)}/kWh')

                # PV Strategy
                if "available_energy_kWh" in device_event["device_info"] and \
                        device_event["device_info"]["available_energy_kWh"] > 0.0:
                    price = self.pv_strategy[0] * device_event["device_info"]["available_energy_kWh"]
                    energy = device_event["device_info"]["available_energy_kWh"]
                    batch_commands[device_event["area_uuid"]] = [
                        {"type": "offer",
                         "price": price,
                         "energy": energy},
                    ]
                    uuid = device_event['area_uuid']
                    print(f'{self.device_uuid_map[uuid]} OFFER {round(energy, 4)} kWh 'f'at {round(price / energy, 2)}/kWh')

                # Battery strategy
                if "energy_to_buy" in device_event["device_info"]:
                    energy_to_buy = device_event["device_info"]["energy_to_buy"] + device_event["device_info"][
                        "offered_buy_kWh"]
                    energy_to_sell = device_event["device_info"]["energy_to_sell"] + device_event["device_info"][
                        "offered_sell_kWh"]
                    batch_commands[device_event["area_uuid"]] = []
                    uuid = device_event['area_uuid']
                    # Battery buy strategy
                    if energy_to_buy > 0.0:
                        buy_price = self.batt_buy_strategy[0] * energy_to_buy
                        buy_energy = energy_to_buy
                        batch_commands[device_event["area_uuid"]].append(
                            {"type": "bid",
                             "price": buy_price,
                             "energy": buy_energy},
                        )
                        print(f'{self.device_uuid_map[uuid]} BID {round(buy_energy, 4)} kWh 'f'at {round(buy_price / buy_energy, 2)}/kWh')
                    # Battery sell strategy
                    if energy_to_sell > 0.0:
                        sell_price = self.batt_sell_strategy[0] * energy_to_sell
                        sell_energy = energy_to_sell
                        batch_commands[device_event["area_uuid"]].append(
                            {"type": "offer",
                             "price": sell_price,
                             "energy": sell_energy},
                        )
                        print(f'{self.device_uuid_map[uuid]} OFFER {round(sell_energy, 4)} kWh 'f'at {round(sell_price / sell_energy, 2)}/kWh')

        # submit list of bids and offers
        if batch_commands:
            response = self.batch_command(batch_commands)

    ################################################
    # TRIGGERS EACH TICK
    ################################################
    def on_tick(self, tick_info):
        print('--------', tick_info['content'][0]['slot_completion'], '--------')
        i = int(float(tick_info['content'][0]['slot_completion'].strip('%')) / ticks) # tick num for index

        ################################################
        # ADJUST BID AND OFFER STRATEGY (if needed)
        ################################################
        # TODO manipulate tick strategy if required
        self.load_strategy = self.load_strategy
        self.pv_strategy = self.pv_strategy
        self.batt_buy_strategy = self.batt_buy_strategy
        self.batt_sell_strategy = self.batt_sell_strategy

        ################################################
        # UPDATE BIDS AND OFFERS EACH TICK (if needed)
        ################################################
        batch_commands = {}
        for device_event in tick_info["content"]:
            if key_in_dict_and_not_none(device_event, "area_uuid"):

                # Load Strategy
                if "energy_requirement_kWh" in device_event["device_info"] and \
                        device_event["device_info"]["energy_requirement_kWh"] > 0.0:
                    price = self.load_strategy[i] * device_event["device_info"]["energy_requirement_kWh"]
                    energy = device_event["device_info"]["energy_requirement_kWh"]
                    batch_commands[device_event["area_uuid"]] = [
                        {"type": "update_bid",
                         "price": price,
                         "energy": energy},
                        ]
                    uuid = device_event['area_uuid']
                    print(f'{self.device_uuid_map[uuid]} BID {round(energy, 4)} kWh 'f'at {round(price / energy, 2)}/kWh')

                # PV Strategy
                if "available_energy_kWh" in device_event["device_info"] and \
                        device_event["device_info"]["available_energy_kWh"] > 0.0:
                    price = self.pv_strategy[i] * device_event["device_info"]["available_energy_kWh"]
                    energy = device_event["device_info"]["available_energy_kWh"]
                    batch_commands[device_event["area_uuid"]] = [
                        {"type": "update_offer",
                         "price": price,
                         "energy": energy},
                        ]
                    uuid = device_event['area_uuid']
                    print(f'{self.device_uuid_map[uuid]} OFFER {round(energy, 4)} kWh 'f'at {round(price / energy, 2)}/kWh')

                # Battery strategy
                if "energy_to_buy" in device_event["device_info"]:
                    energy_to_buy = device_event["device_info"]["energy_to_buy"] + device_event["device_info"]["offered_buy_kWh"]
                    energy_to_sell = device_event["device_info"]["energy_to_sell"] + device_event["device_info"]["offered_sell_kWh"]
                    batch_commands[device_event["area_uuid"]] = []
                    uuid = device_event['area_uuid']
                    # Battery buy strategy
                    if energy_to_buy > 0.0:
                        buy_price = self.batt_buy_strategy[i] * energy_to_buy
                        buy_energy = energy_to_buy
                        batch_commands[device_event["area_uuid"]].append(
                            {"type": "update_bid",
                             "price": buy_price,
                             "energy": buy_energy},
                        )
                        print(f'{self.device_uuid_map[uuid]} BID {round(buy_energy, 4)} kWh 'f'at {round(buy_price / buy_energy, 2)}/kWh')
                    # Battery sell strategy
                    if energy_to_sell > 0.0:
                        sell_price = self.batt_sell_strategy[i] * energy_to_sell
                        sell_energy = energy_to_sell
                        batch_commands[device_event["area_uuid"]].append(
                            {"type": "update_offer",
                             "price": sell_price,
                             "energy": sell_energy},
                        )
                        print(f'{self.device_uuid_map[uuid]} OFFER {round(sell_energy, 4)} kWh 'f'at {round(sell_price / sell_energy, 2)}/kWh')

        # submit list of bids and offers
        if batch_commands:
            response = self.batch_command(batch_commands)

    ################################################
    # TRIGGERS EACH TRADE
    ################################################
    def on_trade(self, trade_info):
        # print trade info on trade event
        for trade in trade_info['content']:
            trade_price = trade['price']
            trade_energy = trade['energy']
            buyer = trade['buyer']
            seller = trade['seller']
            trade_price_per_kWh = trade_price / trade_energy
            if buyer != 'anonymous':
                print(f'<-- {buyer} BOUGHT {round(trade_energy, 4)} kWh 'f'at {round(trade_price_per_kWh, 2)}/kWh')
            if seller != 'anonymous':
                print(f'--> {seller} SOLD {round(trade_energy, 4)} kWh 'f'at {round(trade_price_per_kWh, 2)}/kWh')

    ################################################
    # TRIGGERS EACH COMMAND RESPONSE
    ################################################
    def on_batch_response(self, market_stats):
        pass

    ################################################
    # SIMULATION TERMINATION CONDITION
    ################################################
    def on_finish(self, finish_info):
        self.is_finished = True


################################################
# REGISTER FOR DEVICES AND MARKETS
################################################

from time import sleep
sleep(0.5)

# Set registration parameters based on local or web run
if RUN_ON_D3A_WEB:
    aggr = Oracle(
        simulation_id=simulation_id,
        domain_name=domain_name,
        aggregator_name=oracle_name,
        websockets_domain_name=websocket_domain_name
    )
    DeviceClient = RestDeviceClient
    device_args = {
        "simulation_id": simulation_id,
        "domain_name": domain_name,
        "websockets_domain_name": websocket_domain_name,
        "autoregister": False,
        "start_websocket": False
    }
else:
    aggr = Oracle(
        aggregator_name=oracle_name
    )
    DeviceClient = RedisDeviceClient
    device_args = {
        "autoregister": True,
        "pubsub_thread": aggr.pubsub
    }


# Register selected devices to oracle
def register_device_list(device_names, device_args, device_uuid_map):
    for d in device_names:
        print('Registered device:', d)
        if RUN_ON_D3A_WEB:
            uuid = get_area_uuid_from_area_name_and_collaboration_id(device_args["simulation_id"], d, device_args["domain_name"])
            device_args['device_id'] = uuid
            device_uuid_map[uuid] = d
        else:
            device_args['device_id'] = d
        device = DeviceClient(**device_args)
        if not RUN_ON_D3A_WEB:
            device_uuid_map[device.device_uuid] = device.device_id
        device.select_aggregator(aggr.aggregator_uuid)
    return device_uuid_map

print()
print('Registering devices ...')
device_uuid_map = {}
device_uuid_map = register_device_list(load_names, device_args, device_uuid_map)
device_uuid_map = register_device_list(pv_names, device_args, device_uuid_map)
device_uuid_map = register_device_list(storage_names, device_args, device_uuid_map)

aggr.device_uuid_map = device_uuid_map
print()
print('Summary of devices registered:')
print(aggr.device_uuid_map)
print()

# loop to allow persistence
while not aggr.is_finished:
    sleep(0.5)
