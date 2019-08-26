"""
Copyright 2018 Grid Singularity
This file is part of D3A.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
from logging import getLogger

from d3a.d3a_core.exceptions import D3AException
from d3a.d3a_core.util import retry_function, wait_until_timeout_blocking
from d3a.blockchain.utils import unlock_account, wait_for_node_synchronization

log = getLogger(__name__)


BC_NUM_FACTOR = 10 ** 10


class InvalidBlockchainOffer(D3AException):
    pass


class InvalidBlockchainTrade(D3AException):
    pass


def create_market_contract(bc_interface, duration_s, listeners=[]):
    if not bc_interface:
        return None
    contract = bc_interface.init_contract(
        "Market.sol",
        "Market",
        [
            bc_interface.contracts['ClearingToken'].address,
            duration_s
        ],
        listeners
    )
    clearing_contract_instance = bc_interface.contracts['ClearingToken']
    market_address = contract.address
    unlock_account(bc_interface.chain, bc_interface.chain.eth.accounts[0])
    tx_hash = clearing_contract_instance.functions \
        .globallyApprove(market_address, 10 ** 18) \
        .transact({'from': bc_interface.chain.eth.accounts[0]})
    tx_receipt = bc_interface.chain.eth.waitForTransactionReceipt(tx_hash)
    status = tx_receipt["status"]
    log.debug(f"tx_receipt Status: {status}")
    approve_retval = clearing_contract_instance.events \
        .ApproveClearingMember() \
        .processReceipt(tx_receipt)
    wait_for_node_synchronization(bc_interface)
    assert len(approve_retval) > 0
    assert approve_retval[0]["args"]["approver"] == bc_interface.chain.eth.accounts[0]
    assert approve_retval[0]["args"]["market"] == market_address
    assert approve_retval[0]["event"] == "ApproveClearingMember"
    return contract


@retry_function(max_retries=10)
def create_new_offer(bc_interface, bc_contract, energy, price, seller):
    unlock_account(bc_interface.chain, bc_interface.users[seller].address)
    bc_energy = int(energy * BC_NUM_FACTOR)
    tx_hash = bc_contract.functions.offer(
        bc_energy,
        int(price * BC_NUM_FACTOR)).transact({"from": bc_interface.users[seller].address})
    tx_hash_hex = hex(int.from_bytes(tx_hash, byteorder='big'))
    log.debug(f"tx_hash of New Offer {tx_hash_hex}")

    tx_receipt = bc_interface.chain.eth.waitForTransactionReceipt(tx_hash)
    status = tx_receipt["status"]
    log.debug(f"tx_receipt Status: {status}")
    assert status > 0
    wait_for_node_synchronization(bc_interface)

    def get_offer_id():
        return bc_contract.events.NewOffer().processReceipt(tx_receipt)[0]['args']["offerId"]

    wait_until_timeout_blocking(lambda: get_offer_id() is not 0, timeout=20)

    offer_id = get_offer_id()

    log.debug(f"offer_id: {offer_id}")
    assert offer_id is not 0
    return offer_id


def cancel_offer(bc_interface, bc_contract, offer):
    unlock_account(bc_interface.chain, bc_interface.users[offer.seller].address)
    bc_interface.chain.eth.waitForTransactionReceipt(
        bc_contract.functions.cancel(offer.real_id).transact(
            {"from": bc_interface.users[offer.seller].address}
        )
    )


@retry_function(max_retries=10)
def trade_offer(bc_interface, bc_contract, offer_id, energy, buyer):
    unlock_account(bc_interface.chain, bc_interface.users[buyer].address)
    trade_energy = int(energy * BC_NUM_FACTOR)
    tx_hash = bc_contract.functions.trade(offer_id, trade_energy). \
        transact({"from": bc_interface.users[buyer].address})
    tx_hash_hex = hex(int.from_bytes(tx_hash, byteorder='big'))
    log.debug(f"tx_hash of Trade {tx_hash_hex}")
    tx_receipt = bc_interface.chain.eth.waitForTransactionReceipt(tx_hash)
    status = tx_receipt["status"]
    log.debug(f"tx_receipt Status: {status}")
    assert status > 0

    wait_for_node_synchronization(bc_interface)
    new_trade_retval = bc_contract.events.NewTrade().processReceipt(tx_receipt)
    if len(new_trade_retval) == 0:
        wait_until_timeout_blocking(lambda:
                                    len(bc_contract.events.NewTrade().processReceipt(tx_receipt))
                                    is not 0,
                                    timeout=20)
        new_trade_retval = bc_contract.events.NewTrade().processReceipt(tx_receipt)
        log.debug(f"new_trade_retval after retry: {new_trade_retval}")

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
