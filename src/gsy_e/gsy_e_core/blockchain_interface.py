import uuid

class NonBlockchainInterface:
    def __init__(self, market_id, simulation_id=None):
        self.market_id = market_id
        self.simulation_id = simulation_id
        print(f"new market created with id: {market_id}")


    def create_new_offer(self, energy, price, seller):
        return str(uuid.uuid4())

    def cancel_offer(self, offer):
        pass

    def change_offer(self, offer, original_offer, residual_offer):
        pass

    def handle_blockchain_trade_event(self, offer, buyer, original_offer, residual_offer):
        return str(uuid.uuid4()), residual_offer

    def track_trade_event(self, time_slot, trade):
        pass

import os
from web3 import Web3
from web3.geth import GethPersonal
RPC_URI = os.getenv('RPC_URI', 'https://bc4p.nowum.fh-aachen.de/blockchain')
CHAIN_ID = os.getenv('CHAIN_ID','123321')
web3 = Web3(Web3.HTTPProvider(RPC_URI))
import requests

gp = GethPersonal(web3)

class GethBlockchainInterface:
    def __init__(self, market_id, simulation_id=None):
        self.market_id = market_id
        self.simulation_id = simulation_id
        self.traders = {}

    def create_account(self, trader_id):
        # trader_id is passphrase
        self.traders[trader_id] = gp.new_account(trader_id)
        res = requests.post('https://bc4p.nowum.fh-aachen.de/faucet/api/add_key', json= {'public_key': self.traders[trader_id]})
        print(res)

    def create_new_offer(self, energy, price, seller):
        print(f"create_new_offer: {energy} {price} {seller}")
        return str(uuid.uuid4())

    def cancel_offer(self, offer):
        print(f"cancel_offer: {offer}")
        pass

    def change_offer(self, offer, original_offer, residual_offer):
        print(f"change_offer: {offer} {original_offer} {residual_offer}")
        pass

    def handle_blockchain_trade_event(self, offer, buyer, original_offer, residual_offer):
        print(f"handle_blockchain_trade_event: {offer} {buyer} {original_offer} {residual_offer}")
        return str(uuid.uuid4()), residual_offer

    def track_trade_event(self, time_slot, trade):
        print(f"track_trade_event: {time_slot} {trade}")

        if trade.seller_id not in self.traders.keys():
            self.create_account(trade.seller_id)
        if trade.buyer_id not in self.traders.keys():
            self.create_account(trade.buyer_id)
        
        FROM = self.traders[trade.seller_id]
        TO = self.traders[trade.buyer_id]
        nonce = web3.eth.getTransactionCount(FROM)
        
        gasPrice = web3.toWei('1', 'gwei')
        value = web3.toWei(trade.trade_price, 'gwei')
        tx = {
                'chainId': int(CHAIN_ID),
                'nonce': nonce,
                'from': FROM,
                'to': TO,
                'value': value,
                'gas': 2000000,
                'gasPrice': gasPrice
            }
        try:
            gp.send_transaction(tx, trade.seller_id)
        except Exception as e:
            print(e)


def blockchain_interface_factory(should_use_bc, market_id, simulation_id):
    if should_use_bc:
        return GethBlockchainInterface(market_id, simulation_id)
    else:
        return NonBlockchainInterface(market_id, simulation_id)



if __name__ == '__main__':
    #FROM = os.getenv('PUBLIC_KEY','0x2d558F4633FF8011C27401c0070Fd1E981770B94')
    FROM = gp.new_account('tets')
    res = requests.post('https://bc4p.nowum.fh-aachen.de/faucet/api/add_key', data= {'public_key': FROM})
    print(res)
    nonce = web3.eth.getTransactionCount(FROM)
    gasPrice = web3.toWei('1', 'gwei')
    value = web3.toWei(1, 'gwei')

    # my public_key
    TO = '0x8dC8e161975dC5dD6B0DD6D948bC6d469Ae01cD8'

    tx = {
            'chainId': int(CHAIN_ID),
            'nonce': nonce,
            'from': FROM,
            'to': TO,
            'value': value,
            'gas': 2000000,
            'gasPrice': gasPrice
        }
    gp.send_transaction(tx, self.market_id)