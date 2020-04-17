# flake8: noqa
"""
Template file for a trading strategy through the d3a API client
"""
import json
from time import sleep
from d3a_api_client.redis_device import RedisDeviceClient
from d3a_api_client.redis_market import RedisMarketClient
from d3a_api_client.rest_market import RestMarketClient
from d3a_api_client.rest_device import RestDeviceClient
from pendulum import from_format
from d3a_interface.constants_limits import DATE_TIME_FORMAT
from d3a_api_client.utils import get_area_uuid_from_area_name_and_collaboration_id
import os
TIME_ZONE = "UTC"

################################################
# CONFIGURATIONS
################################################

# DESIGNATE DEVICES AND MARKETS TO MANAGE
market_names = ['community']
load_names = ['h1-load-s'] # e.g. ['h1-load-s', 'h2-load'], first load is 'master' strategy
pv_names = ['h1-pv-s']
storage_names = ['h1-storage-s']

# D3A WEB SETUP
# This section to be used for running on live simulations on d3a.io. Ignore for now.
RUN_ON_D3A_WEB = False # if False, runs to local simulation. If True, runs to D3A web
# Set web username and password
# Note, can also be done using export commands in terminal
# export API_CLIENT_USERNAME=username
# export API_CLIENT_PASSWORD=password
os.environ["API_CLIENT_USERNAME"] = "email@email.com"
os.environ["API_CLIENT_PASSWORD"] = "password here"
# set collaboration information
collab_id = "XXX-XXX"
domain_name = 'TBD'
websockets_domain_name = 'TBD'

################################################
# HELPER FUNCTIONS
################################################

if RUN_ON_D3A_WEB:
    MarketClient = RestMarketClient
    DeviceClient = RestDeviceClient
else:
    MarketClient = RedisMarketClient
    DeviceClient = RedisDeviceClient


class AutoDeviceStrategy(DeviceClient):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.models = []
        self.markets = []
        self.loads = []
        self.pvs = []
        self.storages = []

    @staticmethod
    def _handle_list_sentinel_value(argument):
        return argument if argument is not None else []

    # store references to models, markets, and devices - two phase initialization
    def store_reference(self, models_list=None, markets_list=None, loads_list=None,
                        pvs_list=None, storages_list=None):
        self.models = self._handle_list_sentinel_value(models_list)
        self.markets = self._handle_list_sentinel_value(markets_list)
        self.loads = self._handle_list_sentinel_value(loads_list)
        self.pvs = self._handle_list_sentinel_value(pvs_list)
        self.storages = self._handle_list_sentinel_value(storages_list)

    def bid_energy_print(self, energy, price_per_kWh):
        bid = self.bid_energy(energy, energy * price_per_kWh)
        bid = json.loads(bid['bid'])
        print(f"{self.device_id} bid {round(bid['energy'], 4)} kWh "
              f"at {round(bid['price'] / bid['energy'], 2)}/kWh")

    def offer_energy_print(self, energy, price_per_kWh):
        offer = self.offer_energy(energy, energy * price_per_kWh)
        offer = json.loads(offer['offer'])
        print(
            f"{self.device_id} offer {round(offer['energy'], 4)} kWh "
            f"at {round(offer['price'] / offer['energy'], 2)}/kWh")

    def on_market_cycle(self, market_info):
        """
        Triggered each time a new market is created.
        :param market_info: Incoming message containing the newly-created market info
        :return: None
        """
        ################################################
        # FEATURE EXTRACTION AND PRICE PREDICTIONS
        ################################################

        if self.device_id == MASTER_NAME:
            market_time = from_format(market_info['start_time'], DATE_TIME_FORMAT, tz=TIME_ZONE)
            self.handle_master_device_market_cycle(market_time)
        if 'device_info' in market_info:
            self.handle_load_device_market_cycle(market_info)
            self.handle_pv_device_market_cycle(market_info)
            self.handle_storage_device_market_cycle(market_info)

    def handle_master_device_market_cycle(self, market_time):
        print("============================================")
        print("Market", market_time)
        print('--------', '00%', '--------')

        # request market stats
        slots = []
        times = [15, 30]  # sort most recent to oldest for later algo
        for time in times:
            slots.append(market_time.subtract(minutes=time).format(DATE_TIME_FORMAT))
        for market in self.markets:
            stats = market.list_market_stats(slots)

        # load trading strategy setup
        for l in self.loads:
            # set prices
            l.start_ramp_price_per_kWh = 15
            l.end_ramp_price_per_kWh = 26
            l.max_price_per_kWh = 30.0

        # pv trading strategy setup
        for p in self.pvs:
            # set prices
            p.start_ramp_price_per_kWh = 30
            p.end_ramp_price_per_kWh = 10
            p.min_price_per_kWh = 0.0

        # battery
        for s in self.storages:
            # set prices
            s.buy_start_ramp_price_per_kWh = 10
            s.buy_end_ramp_price_per_kWh = 20
            s.sell_start_ramp_price_per_kWh = 28
            s.sell_end_ramp_price_per_kWh = 23

        ################################################
        # INITIAL DEVICE STRATEGIES
        ################################################

    def handle_load_device_market_cycle(self, market_info):
        # initial load trading strategy
        if 'energy_requirement_kWh' in market_info['device_info']:
            if market_info['device_info']['energy_requirement_kWh'] > 0.0:
                self.min_price_per_kWh = 0.0
                self.energy_to_buy = market_info['device_info']['energy_requirement_kWh']
                self.bid_energy_print(self.energy_to_buy, self.min_price_per_kWh)
            else:
                self.energy_to_buy = 0.

    def handle_pv_device_market_cycle(self, market_info):
        # initial pv trading strategy
        if 'available_energy_kWh' in market_info['device_info']:
            if market_info['device_info']['available_energy_kWh'] > 0.0:
                self.max_price_per_kWh = 29.9
                self.energy_to_sell = market_info['device_info']['available_energy_kWh']
                self.offer_energy_print(self.energy_to_sell, self.max_price_per_kWh)
            else:
                self.energy_to_sell = 0.

    def handle_storage_device_market_cycle(self, market_info):
        # initial battery trading strategy
        # buying
        if 'energy_to_buy' in market_info['device_info']:
            if market_info['device_info']['energy_to_buy'] > 0.0:
                self.min_price_per_kWh = 0.
                self.energy_to_buy = market_info['device_info']['energy_to_buy']
                self.bid_energy_print(self, self.energy_to_buy, self.min_price_per_kWh)
            else:
                self.energy_to_buy = 0.
        # selling
        if 'energy_to_sell' in market_info['device_info']:
            if market_info['device_info']['energy_to_sell'] > 0.0:
                self.max_price_per_kWh = 30.1
                self.energy_to_sell = market_info['device_info']['energy_to_sell']
                self.offer_energy_print(self, self.energy_to_sell, self.max_price_per_kWh)
            else:
                self.energy_to_sell = 0.

    def on_tick(self, tick_info):
        """
        Triggered each time a multiple of 10% of the market slot has been completed.
        :param market_info: Incoming message containing updated market and device info
        :return: None
        """
        ################################################
        # PER TICK TRADING STRATEGY EXECUTION
        ################################################
        # load tick trading strategy
        if self.device_id == MASTER_NAME:
            print('--------', tick_info['slot_completion'], '--------')
        if 'device_info' in tick_info:
            self.handle_load_device_tick(tick_info)
            self.handle_pv_device_tick(tick_info)
            self.handle_storage_device_tick(tick_info)

    def handle_load_device_tick(self, tick_info):
        # load strategy
        if 'energy_requirement_kWh' in tick_info['device_info']:
            self.energy_to_buy = tick_info['device_info']['energy_requirement_kWh']
            if self.energy_to_buy > 0.:
                check = self.delete_bid()
                if tick_info['slot_completion'] >= '90%':  # last ditch max rate
                    self.bid_energy_print(self.energy_to_buy, self.max_price_per_kWh)
                else:  # ramp from lowest to max
                    price_per_kWh = self.start_ramp_price_per_kWh + (
                                self.end_ramp_price_per_kWh - self.start_ramp_price_per_kWh) * (
                                                float(tick_info['slot_completion'][:-1]) - 10) / 70
                    energy = self.device_info()['device_info']['energy_requirement_kWh']
                    if energy > 0.:
                        self.bid_energy_print(energy, price_per_kWh)

    def handle_pv_device_tick(self, tick_info):
        # pv strategy
        if 'available_energy_kWh' in tick_info['device_info']:
            self.energy_to_sell = tick_info['device_info']['available_energy_kWh']
            if self.energy_to_sell > 0.:
                check = self.delete_offer()
                if tick_info['slot_completion'] >= '90%':  # last ditch max rate
                    self.offer_energy_print(self.energy_to_sell, self.min_price_per_kWh)
                else:  # ramp from lowest to max
                    price_per_kWh = \
                        self.start_ramp_price_per_kWh - (
                            self.start_ramp_price_per_kWh - self.end_ramp_price_per_kWh) * (
                                            float(tick_info['slot_completion'][:-1]) - 10) / 70
                    energy = self.device_info()['device_info']['available_energy_kWh']
                    if energy > 0.:
                        self.offer_energy_print(energy, price_per_kWh)

    def handle_storage_device_tick(self, tick_info):
        # battery strategy
        if 'energy_to_buy' in tick_info['device_info']:
            self.energy_to_buy = tick_info['device_info']['energy_to_buy']
            if self.energy_to_buy > 0.:
                self.delete_bid()
                price_per_kWh = \
                    self.buy_start_ramp_price_per_kWh + (
                        self.buy_end_ramp_price_per_kWh - self.buy_start_ramp_price_per_kWh) * (
                        float(tick_info['slot_completion'][:-1]) - 10) / 80
                energy = self.device_info()['device_info']['energy_to_buy']
                if energy > 0.:
                    self.bid_energy_print(energy, price_per_kWh)
        if 'energy_to_sell' in tick_info['device_info']:
            self.energy_to_sell = tick_info['device_info']['energy_to_sell']
            if self.energy_to_sell > 0.:
                self.delete_offer()
                price_per_kWh = \
                    self.sell_start_ramp_price_per_kWh - (
                        self.sell_start_ramp_price_per_kWh - self.sell_end_ramp_price_per_kWh) * (
                                        float(tick_info['slot_completion'][:-1]) - 10) / 80
                energy = self.device_info()['device_info']['energy_to_sell']
                if energy > 0.:
                    self.offer_energy_print(energy, price_per_kWh)

    def on_trade(self, trade_info):
        """
        Triggered each time a trade occurs.
        :param trade_info: Incoming message about the trade
        :return: None
        """

        ################################################
        # TRADE EVENT HANDLING
        ################################################

        # TODO Note that more info is currently passed than you should have.
        # TODO You will only have a trade confirmation and price / energy amount at the hack.

        # buyer
        if trade_info['buyer'] == self.device_id:
            offer = json.loads(trade_info['offer'])
            trade_price = offer['price']
            trade_energy = offer['energy']
            trade_price_per_kWh = trade_price / trade_energy
            print(f'<-- {self.device_id} BOUGHT {round(trade_energy, 4)} kWh '
                  f'at {round(trade_price_per_kWh,2)}/kWh')

        # seller
        if trade_info['seller'] == self.device_id:
            offer = json.loads(trade_info['offer'])
            trade_price = offer['price']
            trade_energy = offer['energy']
            self.energy_to_sell -= trade_energy
            trade_price_per_kWh = trade_price / trade_energy
            print(f'--> {self.device_id} SOLD {round(trade_energy, 4)} kWh '
                  f'at {round(trade_price_per_kWh,2)}/kWh')


    def on_finish(self, finish_info):
        """
        Triggered each time a new market is created.
        :param message: Incoming message about finished simulation
        :return: None
        """
        print(f"Simulation finished. Information: {finish_info}")

################################################
# REGISTER MARKETS AND DEVICES
################################################


def register_list(device_flag, asset_list, collaboration_id=None,
                  domain=None, websockets_domain=None):
    device_key_name = "device_id" if device_flag else "area_id"
    if RUN_ON_D3A_WEB:
        asset_list = [
            get_area_uuid_from_area_name_and_collaboration_id(collaboration_id, n, domain_name)
            for n in asset_list
        ]

        kwargs_list = [{
            "simulation_id": collaboration_id,
            "device_id": a,
            "domain_name": domain,
            "websockets_domain_name": websockets_domain
        } for a in asset_list]
    else:
        kwargs_list = [{
            device_key_name: a
        } for a in asset_list]

    if device_flag:
        return [
            AutoDeviceStrategy(**kwargs, autoregister=True)
            for kwargs in kwargs_list
        ]
    else:
        return [
            MarketClient(**kwargs)
            for kwargs in kwargs_list
        ]


if __name__ == '__main__':

    kwargs = {
        "collaboration_id": collab_id,
        "domain": domain_name,
        "websockets_domain": websockets_domain_name
    }

    # register for markets to get information
    markets = register_list(device_flag=False, asset_list=market_names, **kwargs)

    # register for loads
    loads = register_list(device_flag=True, asset_list=load_names, **kwargs)
    MASTER_NAME = loads[0].device_id

    # register for pvs
    pvs = register_list(device_flag=True, asset_list=pv_names, **kwargs)

    # register for storages
    storages = register_list(device_flag=True, asset_list=storage_names, **kwargs)


    ################################################
    # LOAD PREDICTION MODELS
    ################################################

    # load models
    prediction_models = []

    ################################################
    # CREATE REFERENCES FOR MASTER STRATEGY
    ################################################

    # allow devices to be called within master method
    loads[0].store_reference(models_list=prediction_models, markets_list=markets,
                             loads_list=loads, pvs_list=pvs, storages_list=storages)

    # infinite loop to allow client to run in the background
    while True:
        sleep(0.1)
