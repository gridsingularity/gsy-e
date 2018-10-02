import pytest
from solc import compile_source
from web3.contract import Contract
from eth_utils import to_bytes

from d3a.util import get_cached_joined_contract_source
from .token_fixtures import blockchain_fixture # NOQA


@pytest.fixture # NOQA
def _bc(blockchain_fixture):
    yield blockchain_fixture


emptybytes = b'\x00' * 32
zero_address = '0' * 40
zero_address_hex = '0x' + zero_address

market_compiled_sol = compile_source(get_cached_joined_contract_source("Market.sol"))
market_contract_interface = market_compiled_sol['<stdin>:Market']

clearing_compiled_sol = compile_source(get_cached_joined_contract_source("ClearingToken.sol"))
clearing_contract_interface = market_compiled_sol['<stdin>:ClearingToken']


def make_market_contract(_bc, approver, constructor_params):
    market_contract = _bc.eth.contract(abi=market_contract_interface['abi'],
                                       bytecode=market_contract_interface['bin'])
    tx_hash = market_contract.constructor(*constructor_params).transact({'from': approver})
    market_address = _bc.eth.waitForTransactionReceipt(tx_hash).contractAddress
    market_instance = _bc.eth.contract(address=market_address,
                                       abi=market_contract_interface['abi'],
                                       ContractFactoryClass=Contract)
    return market_instance, market_address


def place_offer_and_return_offerid(market_contract, energy_units, price, sender, _bc):
    tx_hash = market_contract.functions.offer(energy_units, price).transact({"from": sender})
    tx_receipt = _bc.eth.waitForTransactionReceipt(tx_hash)
    offer_retval = market_contract.events.NewOffer().processReceipt(tx_receipt)
    return offer_retval[0]['args']["offerId"] if len(offer_retval) else 0


def perform_trade_and_return_offer_changed_trade_event(market_contract, offerid, energy, sender,
                                                       _bc):
    tx_hash = market_contract.functions.trade(offerid, energy).transact({'from': sender})
    tx_receipt = _bc.eth.waitForTransactionReceipt(tx_hash)
    new_trade = market_contract.events.NewTrade().processReceipt(tx_receipt)
    offer_changed = market_contract.events.OfferChanged().processReceipt(tx_receipt)
    return new_trade, offer_changed


@pytest.fixture
def base_state_contract(_bc):
    clearing_contract = _bc.eth.contract(abi=clearing_contract_interface['abi'],
                                         bytecode=clearing_contract_interface['bin'])
    tx_hash = clearing_contract.constructor(10 ** 5, "ClearingToken", 5, "CT"). \
        transact({'from': _bc.eth.accounts[0]})
    clearing_address = _bc.eth.waitForTransactionReceipt(tx_hash).contractAddress
    clearing_contract_instance = _bc.eth.contract(address=clearing_address,
                                                  abi=clearing_contract_interface['abi'],
                                                  ContractFactoryClass=Contract)

    market_contract = _bc.eth.contract(abi=market_contract_interface['abi'],
                                       bytecode=market_contract_interface['bin'])
    tx_hash = market_contract.constructor(clearing_address, 3 * 60). \
        transact({'from': _bc.eth.accounts[0]})
    market_address = _bc.eth.waitForTransactionReceipt(tx_hash).contractAddress
    market_contract_instance = _bc.eth.contract(address=market_address,
                                                abi=market_contract_interface['abi'],
                                                ContractFactoryClass=Contract)

    # Globally approve
    tx_hash = clearing_contract_instance.functions.globallyApprove(market_address, 1000000). \
        transact({'from': _bc.eth.accounts[0]})
    tx_receipt = _bc.eth.waitForTransactionReceipt(tx_hash)
    approve_retval = clearing_contract_instance.events.ApproveClearingMember(). \
        processReceipt(tx_receipt)
    assert len(approve_retval) > 0
    assert approve_retval[0]["args"]["approver"] == _bc.eth.accounts[0]
    assert approve_retval[0]["args"]["market"] == market_address
    assert approve_retval[0]["event"] == "ApproveClearingMember"
    return clearing_contract_instance, clearing_address, market_contract_instance, market_address


def test_approver(base_state_contract, _bc):
    clearing_contract, clearing_address, market_contract, market_address = base_state_contract
    assert clearing_contract.functions.getApprover().call() == _bc.eth.accounts[0]


def test_globallyApprove(base_state_contract, _bc):
    clearing_contract, clearing_address, market_contract, market_address = base_state_contract
    assert clearing_contract.functions.globallyApprove(market_address, 1000). \
        transact({"from": _bc.eth.accounts[0]})


def test_offer(base_state_contract, _bc):
    clearing_contract, clearing_address, market_contract, market_address = base_state_contract
    offer_id = place_offer_and_return_offerid(market_contract, 7, 956,
                                              _bc.eth.accounts[1], _bc)
    assert market_contract.functions.getOffer(offer_id).call() == [7, 956, _bc.eth.accounts[1]]


def test_offer_fail(base_state_contract, _bc):
    clearing_contract, clearing_address, market_contract, market_address = base_state_contract
    offer_id = place_offer_and_return_offerid(market_contract, 0, 956,
                                              _bc.eth.accounts[1], _bc)
    assert market_contract.functions.getOffer(to_bytes(offer_id)).call() == \
        [0, 0, zero_address_hex]


def test_cancel(base_state_contract, _bc):
    clearing_contract, clearing_address, market_contract, market_address = base_state_contract
    offer_id = place_offer_and_return_offerid(market_contract, 7, 956,
                                              _bc.eth.accounts[1], _bc)
    assert market_contract.functions.getOffer(offer_id).call() == [7, 956, _bc.eth.accounts[1]]
    tx_hash = market_contract.functions.cancel(offer_id).transact({"from": _bc.eth.accounts[1]})
    tx_receipt = _bc.eth.waitForTransactionReceipt(tx_hash)
    cancel_retval = market_contract.events.CancelOffer().processReceipt(tx_receipt)
    assert cancel_retval[0]['args']['energyUnits'] == 7
    assert cancel_retval[0]['args']['price'] == 956
    assert cancel_retval[0]['args']['seller'] == _bc.eth.accounts[1]

    assert market_contract.functions.getOffer(offer_id).call() == [0, 0, zero_address_hex]


def test_get_clearing_token_address(base_state_contract):
    clearing_contract, clearing_address, market_contract, market_address = base_state_contract
    assert market_contract.functions.getClearingTokenAddress().call() == clearing_address


def test_trade(base_state_contract, _bc):
    clearing_contract, clearing_address, market_contract, market_address = base_state_contract

    tx_hash = market_contract.functions.offer(7, 956).transact({'from': _bc.eth.accounts[1]})
    tx_receipt = _bc.eth.waitForTransactionReceipt(tx_hash)
    offer_retval = market_contract.events.NewOffer().processReceipt(tx_receipt)
    offer_id = offer_retval[0]['args']["offerId"]
    assert market_contract.functions.getClearingTokenAddress().call() == clearing_address
    tx_hash = market_contract.functions.trade(offer_id, 7). \
        transact({'from': _bc.eth.accounts[2], 'gas': 4712388})
    tx_receipt = _bc.eth.waitForTransactionReceipt(tx_hash)
    new_trade_retval = market_contract.events.NewTrade().processReceipt(tx_receipt)
    offer_changed_retval = market_contract.events.OfferChanged().processReceipt(tx_receipt)
    assert offer_changed_retval == ()
    assert new_trade_retval[0]["args"]["tradeId"] != emptybytes
    assert clearing_contract.functions.balanceOf(_bc.eth.accounts[2]).call() == -6692
    assert clearing_contract.functions.balanceOf(
        new_trade_retval[0]["args"]["buyer"]).call() == -6692
    assert clearing_contract.functions.balanceOf(_bc.eth.accounts[1]).call() == 6692
    assert clearing_contract.functions.balanceOf(
        new_trade_retval[0]["args"]["seller"]).call() == 6692


def test_partial_trade(base_state_contract, _bc):
    clearing_contract, clearing_address, market_contract, market_address = base_state_contract
    offer_id = place_offer_and_return_offerid(market_contract, 7, 956,
                                              _bc.eth.accounts[1], _bc)

    tx_hash = market_contract.functions.trade(offer_id, 4). \
        transact({'from': _bc.eth.accounts[2], 'gas': 4712388})
    tx_receipt = _bc.eth.waitForTransactionReceipt(tx_hash)
    new_trade_retval = market_contract.events.NewTrade().processReceipt(tx_receipt)
    offer_changed_retval = market_contract.events.OfferChanged().processReceipt(tx_receipt)
    assert offer_changed_retval != ()
    assert offer_changed_retval[0]["args"]["oldOfferId"] == offer_id
    assert offer_changed_retval[0]["args"]["energyUnits"] == 3
    assert offer_changed_retval[0]["args"]["price"] == 956
    new_offer_id = offer_changed_retval[0]["args"]["newOfferId"]
    assert new_offer_id != emptybytes
    assert market_contract.functions.getOffer(new_offer_id).call() == \
        [3, 956, _bc.eth.accounts[1]]

    assert new_trade_retval != ()
    assert new_trade_retval[0]["args"]["tradeId"] != emptybytes
    assert new_trade_retval[0]["args"]["energyUnits"] == 4
    assert new_trade_retval[0]["args"]["price"] == 956
    assert new_trade_retval[0]["args"]["buyer"] == _bc.eth.accounts[2]
    assert new_trade_retval[0]["args"]["seller"] == _bc.eth.accounts[1]

    assert clearing_contract.functions.balanceOf(_bc.eth.accounts[2]).call() == -3824
    assert clearing_contract.functions.balanceOf(
        new_trade_retval[0]["args"]["buyer"]).call() == -3824
    assert clearing_contract.functions.balanceOf(_bc.eth.accounts[1]).call() == 3824
    assert clearing_contract.functions.balanceOf(
        new_trade_retval[0]["args"]["seller"]).call() == 3824
    assert market_contract.functions.balanceOf(_bc.eth.accounts[2]).call() == 4
    assert market_contract.functions.balanceOf(_bc.eth.accounts[1]).call() == -4


def test_seller_trade_fail(base_state_contract, _bc):
    """Checks if msg.sender == offer.seller then trade should fail"""
    clearing_contract, clearing_address, market_contract, market_address = base_state_contract
    offer_id = place_offer_and_return_offerid(market_contract, 7, 956,
                                              _bc.eth.accounts[1], _bc)

    new_trade_retval, offer_changed_retval = perform_trade_and_return_offer_changed_trade_event(
        market_contract, offer_id, 4, _bc.eth.accounts[1], _bc
    )
    assert offer_changed_retval == ()
    assert new_trade_retval == ()


def test_offer_price_negative(base_state_contract, _bc):
    """
    Scenario where you need to get rid of your energy and you pay the
    buyer to take your excess energy. Difference is offer price is negative.
    """
    clearing_contract, clearing_address, market_contract, market_address = base_state_contract
    offer_id = place_offer_and_return_offerid(market_contract, 7, -10,
                                              _bc.eth.accounts[2], _bc)
    new_trade_retval, offer_changed_retval = perform_trade_and_return_offer_changed_trade_event(
        market_contract, offer_id, 7, _bc.eth.accounts[1], _bc
    )
    assert offer_changed_retval == ()
    assert new_trade_retval != ()
    assert new_trade_retval[0]["args"]["tradeId"] != emptybytes
    assert new_trade_retval[0]["args"]["energyUnits"] == 7
    assert new_trade_retval[0]["args"]["price"] == -10
    assert new_trade_retval[0]["args"]["buyer"] == _bc.eth.accounts[1]
    assert new_trade_retval[0]["args"]["seller"] == _bc.eth.accounts[2]
    assert clearing_contract.functions.balanceOf(_bc.eth.accounts[1]).call() == 70
    assert clearing_contract.functions.balanceOf(_bc.eth.accounts[2]).call() == -70


def test_offer_price_zero(base_state_contract, _bc):
    clearing_contract, clearing_address, market_contract, market_address = base_state_contract
    offer_id = place_offer_and_return_offerid(market_contract, 7, 0, _bc.eth.accounts[2], _bc)
    assert market_contract.functions.getOffer(offer_id).call() == [7, 0, _bc.eth.accounts[2]]

    new_trade_retval, offer_changed_retval = perform_trade_and_return_offer_changed_trade_event(
        market_contract, offer_id, 7, _bc.eth.accounts[1], _bc
    )
    assert offer_changed_retval == ()
    assert new_trade_retval != ()
    assert new_trade_retval[0]["args"]["tradeId"] != emptybytes
    assert new_trade_retval[0]["args"]["energyUnits"] == 7
    assert new_trade_retval[0]["args"]["price"] == 0
    assert new_trade_retval[0]["args"]["buyer"] == _bc.eth.accounts[1]
    assert new_trade_retval[0]["args"]["seller"] == _bc.eth.accounts[2]
    assert clearing_contract.functions.balanceOf(_bc.eth.accounts[1]).call() == 0
    assert clearing_contract.functions.balanceOf(_bc.eth.accounts[2]).call() == 0
    assert market_contract.functions.balanceOf(_bc.eth.accounts[1]).call() == 7
    assert market_contract.functions.balanceOf(_bc.eth.accounts[2]).call() == -7
    assert market_contract.functions.getOffer(offer_id).call() == [0, 0, '0x' + zero_address]


def test_multiple_markets(_bc, base_state_contract):
    clearing_contract, clearing_address, market_contract_a, market_address_a = base_state_contract
    market_contract_b, market_address_b = make_market_contract(_bc,
                                                               _bc.eth.accounts[0],
                                                               [clearing_address, 4 * 60])
    assert market_address_a != market_address_b
    _bc.eth.waitForTransactionReceipt(
        clearing_contract.functions.globallyApprove(market_address_b, 1000000)
        .transact({'from': _bc.eth.accounts[0]})
    )

    offerid_a = place_offer_and_return_offerid(market_contract_a, 8, 790,
                                               _bc.eth.accounts[1], _bc)
    offerid_b = place_offer_and_return_offerid(market_contract_b, 9, 899,
                                               _bc.eth.accounts[2], _bc)
    new_trade_a, offer_changed_a = perform_trade_and_return_offer_changed_trade_event(
        market_contract_a, offerid_a, 8, _bc.eth.accounts[3], _bc
    )
    assert offer_changed_a == ()
    assert new_trade_a != ()
    new_trade_b, offer_changed_b = perform_trade_and_return_offer_changed_trade_event(
        market_contract_b, offerid_b, 9, _bc.eth.accounts[4], _bc
    )
    assert offer_changed_b == ()
    assert new_trade_b != ()

    assert clearing_contract.functions.balanceOf(_bc.eth.accounts[3]).call() == -6320
    assert clearing_contract.functions.balanceOf(_bc.eth.accounts[1]).call() == 6320
    assert clearing_contract.functions.balanceOf(_bc.eth.accounts[4]).call() == -8091
    assert clearing_contract.functions.balanceOf(_bc.eth.accounts[2]).call() == 8091


@pytest.mark.skip(reason="depends on the ability to change the block timestamp of the blockchain.")
def test_trade_fail_afterinterval(base_state_contract, _bc):
    clearing_contract, clearing_address, market_contract, market_address = base_state_contract

    offer_id_a = place_offer_and_return_offerid(market_contract, 7, 956,
                                                _bc.eth.accounts[1], _bc)
    assert market_contract.functions.getOffer(offer_id_a).call() == [7, 956, _bc.eth.accounts[1]]

    offer_id_b = place_offer_and_return_offerid(market_contract, 8, 799,
                                                _bc.eth.accounts[2], _bc)
    assert market_contract.functions.getOffer(offer_id_b).call() == [8, 799, _bc.eth.accounts[2]]

    _bc.block.timestamp += 2 * 60

    new_trade, offer_changed = perform_trade_and_return_offer_changed_trade_event(
        market_contract, offer_id_a, 7, _bc.eth.accounts[3], _bc
    )
    assert offer_changed == ()
    assert new_trade != ()
    assert clearing_contract.functions.balanceOf(_bc.eth.accounts[3]).call() == -6692
    assert clearing_contract.functions.balanceOf(_bc.eth.accounts[1]).call() == 6692

    # making block.timestamp more than the interval of the market_contract
    _bc.block.timestamp += 4 * 60
    new_trade, offer_changed = perform_trade_and_return_offer_changed_trade_event(
        market_contract, offer_id_b, 8, _bc.eth.accounts[4], _bc
    )
    assert new_trade == ()
    assert offer_changed == ()
    assert clearing_contract.functions.balanceOf(_bc.eth.accounts[2]).call() == 0
    assert clearing_contract.functions.balanceOf(_bc.eth.accounts[4]).call() == 0


@pytest.mark.skip(reason="depends on whether an exception should be raised, "
                         "now it is silenced.")
def test_trade_fail_on_clearingTransfer_fail(base_state_contract, _bc):
    """
    Raises an exception because energy should not be transferred
    if money transaction fails in the trade function
    """
    clearing_contract, clearing_address, market_contract, market_address = base_state_contract

    offer_id = place_offer_and_return_offerid(market_contract, 7, 956,
                                              _bc.eth.accounts[1], _bc)
    with pytest.raises(Exception):
        perform_trade_and_return_offer_changed_trade_event(
            market_contract, offer_id, 8, _bc.eth.accounts[2], _bc
        )
    assert clearing_contract.functions.balanceOf(_bc.eth.accounts[1]).call() == 0
    assert clearing_contract.functions.balanceOf(_bc.eth.accounts[2]).call() == 0
    assert market_contract.functions.balanceOf(_bc.eth.accounts[1]).call() == 0
    assert market_contract.functions.balanceOf(_bc.eth.accounts[2]).call() == 0
