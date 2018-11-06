import uuid
from collections import defaultdict, namedtuple
from logging import getLogger
from typing import Dict, List, Optional  # noqa
from web3 import Web3, HTTPProvider
from solc import compile_source
from web3.contract import Contract
from subprocess import Popen, DEVNULL
from d3a.models.events import MarketEvent

from d3a.util import get_cached_joined_contract_source, wait_until_timeout_blocking
from d3a.blockchain.users import BCUsers
from d3a.blockchain.utils import unlock_account, wait_for_node_synchronization
from d3a.models.const import ConstSettings
from d3a.exceptions import InvalidTrade


log = getLogger(__name__)


User = namedtuple('User', ('name', 'address', 'privkey'))

BC_NUM_FACTOR = 10 ** 10


class InvalidBlockchainOffer(Exception):
    pass


class InvalidBlockchainTrade(Exception):
    pass


BC_EVENT_MAP = {
    b"NewOffer": MarketEvent.OFFER,
    b"CancelOffer": MarketEvent.OFFER_DELETED,
    b"NewTrade": MarketEvent.TRADE,
    b"OfferChanged": MarketEvent.OFFER_CHANGED
}


class BlockChainInterface:
    def __init__(self, default_user_balance=10 ** 8):
        if ConstSettings.BlockchainSettings.START_LOCAL_CHAIN:
            self._ganache_process = Popen(['ganache-cli', '-a', '50', '-e', '10000000000'],
                                          close_fds=False, stdout=DEVNULL, stderr=DEVNULL)
            self.chain = Web3(HTTPProvider(ConstSettings.BlockchainSettings.URL))
            log.info("Launching Ganache Blockchain")

        else:
            self.chain = Web3(HTTPProvider(ConstSettings.BlockchainSettings.URL))
            log.info("Connected to Remote Blockchain")

            wait_until_timeout_blocking(lambda: self.chain.net.peerCount > 0, timeout=20)
            log.info(f"Number of Peers: {self.chain.net.peerCount}")

        self.contracts = {}  # type: Dict[str, Contract]
        self.users = BCUsers(self.chain, self.contracts, default_user_balance)
        self.listeners = defaultdict(list)  # type: Dict[str, List[callable]]
        self.init_contract("ClearingToken.sol", "ClearingToken", [10 ** 10,
                                                                  "ClearingToken", 0,
                                                                  "CT"],
                           id_='ClearingToken')

    def init_contract(self, contract_filename: str, contract_name: str,
                      args: list, listeners: Optional[List] = None, id_: str = None):

        log.debug("Initializing contract '%s'", contract_name)
        compiled_sol = compile_source(get_cached_joined_contract_source(contract_filename))
        contract_interface = compiled_sol['<stdin>:' + contract_name]

        contract = self.chain.eth.contract(abi=contract_interface['abi'],
                                           bytecode=contract_interface['bin'])
        unlock_account(self.chain, self.chain.eth.accounts[0])
        tx_hash = contract.constructor(*args).transact({'from': self.chain.eth.accounts[0]})
        wait_until_timeout_blocking(lambda: self.chain.eth.waitForTransactionReceipt(tx_hash).
                                    contractAddress is not None, timeout=20)
        contract_address = self.chain.eth.waitForTransactionReceipt(tx_hash).contractAddress
        contract = self.chain.eth.contract(address=contract_address,
                                           abi=contract_interface['abi'],
                                           ContractFactoryClass=Contract)
        log.info(f"{contract_name} SmartContract deployed with Address: {contract_address}")
        self.contracts[contract.address] = contract
        if id_:
            self.contracts[id_] = contract
        if listeners:
            self.listeners[contract.address].extend(listeners)
        return contract

    def create_market_contract(self, duration_s, listeners=[]):
        contract = self.init_contract(
            "Market.sol",
            "Market",
            [
                self.contracts['ClearingToken'].address,
                duration_s
            ],
            listeners
        )
        clearing_contract_instance = self.contracts['ClearingToken']
        market_address = contract.address
        unlock_account(self.chain, self.chain.eth.accounts[0])
        tx_hash = clearing_contract_instance.functions \
            .globallyApprove(market_address, 10 ** 18) \
            .transact({'from': self.chain.eth.accounts[0]})
        tx_receipt = self.chain.eth.waitForTransactionReceipt(tx_hash)
        approve_retval = clearing_contract_instance.events \
            .ApproveClearingMember() \
            .processReceipt(tx_receipt)
        wait_for_node_synchronization(self)
        assert len(approve_retval) > 0
        assert approve_retval[0]["args"]["approver"] == self.chain.eth.accounts[0]
        assert approve_retval[0]["args"]["market"] == market_address
        assert approve_retval[0]["event"] == "ApproveClearingMember"
        return contract

    def create_new_offer(self, bc_contract, energy, price, seller):
        if not bc_contract:
            return str(uuid.uuid4())
        else:
            unlock_account(self.chain, self.users[seller].address)
            bc_energy = int(energy * BC_NUM_FACTOR)
            tx_hash = bc_contract.functions.offer(
                bc_energy,
                int(price * BC_NUM_FACTOR)).transact({"from": self.users[seller].address})
            tx_hash_hex = hex(int.from_bytes(tx_hash, byteorder='big'))
            log.info(f"tx_hash of New Offer {tx_hash_hex}")

            tx_receipt = self.chain.eth.waitForTransactionReceipt(tx_hash)
            wait_for_node_synchronization(self)
            offer_id = \
                bc_contract.events.NewOffer().processReceipt(tx_receipt)[0]['args']["offerId"]

            wait_until_timeout_blocking(lambda:
                                        bc_contract.functions.getOffer(offer_id).call() is not 0,
                                        timeout=20)

            return offer_id

    def cancel_offer(self, bc_contract, offer_id, seller):
        if bc_contract and offer_id:
            unlock_account(self.chain, self.users[seller].address)
            self.chain.eth.waitForTransactionReceipt(
                bc_contract.functions.cancel(offer_id).transact(
                    {"from": self.users[seller].address}
                )
            )

    def trade_offer(self, bc_contract, offer_id, energy, buyer):
        unlock_account(self.chain, self.users[buyer].address)
        trade_energy = int(energy * BC_NUM_FACTOR)
        tx_hash = bc_contract.functions.trade(offer_id, trade_energy). \
            transact({"from": self.users[buyer].address})
        tx_hash_hex = hex(int.from_bytes(tx_hash, byteorder='big'))
        log.info(f"tx_hash of Trade {tx_hash_hex}")
        tx_receipt = self.chain.eth.waitForTransactionReceipt(tx_hash)
        wait_for_node_synchronization(self)
        new_trade_retval = bc_contract.events.NewTrade().processReceipt(tx_receipt)
        print(f"new_trade_retval: {new_trade_retval}")

        wait_until_timeout_blocking(lambda: len(bc_contract.events.NewTrade().
                                                processReceipt(tx_receipt)) != 0,
                                    timeout=20)

        new_trade_retval = bc_contract.events.NewTrade().processReceipt(tx_receipt)
        print(f"new_trade_retval: {new_trade_retval}")

        offer_changed_retval = bc_contract.events \
            .OfferChanged() \
            .processReceipt(tx_receipt)

        if len(offer_changed_retval) > 0 and \
                not offer_changed_retval[0]['args']['success']:
            raise InvalidBlockchainOffer(f"Invalid blockchain offer changed. Transaction return "
                                         f"value {offer_changed_retval}")

        if not new_trade_retval[0]['args']['success']:
            raise InvalidBlockchainTrade(f"Invalid blockchain trade. Transaction return "
                                         f"value {new_trade_retval}")

        trade_id = new_trade_retval[0]['args']['tradeId']
        new_offer_id = offer_changed_retval[0]['args']['newOfferId'] \
            if len(offer_changed_retval) > 0 \
            else None
        return trade_id, new_offer_id

    def handle_blockchain_trade_event(self, offer, buyer, bc_contract,
                                      original_offer, residual_offer):
        if not bc_contract:
            return str(uuid.uuid4())
        else:
            trade_id, new_offer_id = self.trade_offer(bc_contract,
                                                      offer.real_id, offer.energy, buyer)

            if residual_offer is not None:
                if new_offer_id is None:
                    raise InvalidTrade("Blockchain and local residual offers are out of sync")
                residual_offer.id = str(new_offer_id)
                residual_offer.real_id = new_offer_id
            return trade_id, residual_offer

    def bc_listener(self):
        # TODO: Disabled for now, should be added once event driven blockchain transaction
        # handling is introduced
        # event_type = BC_EVENT_MAP[event['_event_type']]
        # kwargs = {}
        # if event_type is MarketEvent.OFFER:
        #     kwargs['offer'] = interface.offers[event['offerId']]
        # elif event_type is MarketEvent.OFFER_DELETED:
        #     kwargs['offer'] = interface.offers_deleted.pop(event['offerId'])
        # elif event_type is MarketEvent.OFFER_CHANGED:
        #     existing_offer, new_offer = interface.offers_changed.pop(event['oldOfferId'])
        #     kwargs['existing_offer'] = existing_offer
        #     kwargs['new_offer'] = new_offer
        # elif event_type is MarketEvent.TRADE:
        #     kwargs['trade'] = interface._trades_by_id.pop(event['tradeId'])
        # interface._notify_listeners(event_type, **kwargs)
        return
