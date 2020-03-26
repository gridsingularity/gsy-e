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
else:
    MarketClient = RedisMarketClient


class AutoMarketStrategy(MarketClient):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.models = []
        self.markets = []

    @staticmethod
    def _handle_list_sentinel_value(argument):
        return argument if argument is not None else []

    # store references to models, markets, and devices - two phase initialization
    def store_reference(self, models_list=None, markets_list=None, loads_list=None,
                        pvs_list=None, storages_list=None):
        self.models = self._handle_list_sentinel_value(models_list)
        self.markets = self._handle_list_sentinel_value(markets_list)

    def change_fee_print(self, energy, price_per_kWh):
        # TODO update with changed grid fee
        bid = self.bid_energy(energy, energy * price_per_kWh)
        bid = json.loads(bid['bid'])
        print(f"{self.device_id} bid {round(bid['energy'], 4)} kWh "
              f"at {round(bid['price'] / bid['energy'], 2)}/kWh")

    def on_market_cycle(self, market_info):
        """
        Triggered each time a new market is created.
        :param market_info: Incoming message containing the newly-created market info
        :return: None
        """
        print(market_info)
        ################################################
        # FEATURE EXTRACTION AND PRICE PREDICTIONS
        ################################################

        if self.device_id == MASTER_NAME:
            market_time = from_format(market_info['start_time'], DATE_TIME_FORMAT, tz=TIME_ZONE)
            self.handle_master_market_market_cycle(market_time)

    def handle_master_market_market_cycle(self, market_time):
        print("============================================")
        print("Market", market_time)
        print('--------', '00%', '--------')

        # request market stats
        slots = []
        times = [15, 30]  # sort most recent to oldest for later algo
        for time in times:
            slots.append(market_time.subtract(minutes=time).format(DATE_TIME_FORMAT))
        for market in self.markets:
            stats = market.list_dso_stats(slots)


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
        device_key_name = "area_id"
        kwargs_list = [{
            device_key_name: a
        } for a in asset_list]

    return [
        AutoMarketStrategy(**kwargs)
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
    MASTER_NAME = markets[0].area_id

    ################################################
    # LOAD PREDICTION MODELS
    ################################################

    # load models
    prediction_models = []

    ################################################
    # CREATE REFERENCES FOR MASTER STRATEGY
    ################################################

    # allow devices to be called within master method
    markets[0].store_reference(models_list=prediction_models, markets_list=markets)

    # infinite loop to allow client to run in the background
    while True:
        sleep(0.1)
