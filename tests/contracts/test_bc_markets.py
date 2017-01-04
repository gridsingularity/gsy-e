from contextlib import contextmanager

import pytest
from ethereum import tester
from ethereum.utils import encode_hex

from d3a import get_contract_path

# setup accounts
accounts = tester.accounts
keys = tester.keys
A, B, C, D, E, F, G, H = accounts[:8]
A_key, B_key, C_key, D_key, E_key, F_key, G_key, H_key = keys[:8]


# contract paths
market_contract_path = get_contract_path('Market.sol')
clearing_contract_path = get_contract_path('ClearingToken.sol')
state = tester.state()


def make_market_contract(approver, constructor_params):
    return state.abi_contract(None, path=market_contract_path,
                              language='solidity',
                              sender=approver,
                              constructor_parameters=constructor_params)


@contextmanager
def print_gas_used(state, string):
    t_gas = state.block.gas_used
    yield
    gas_used = state.block.gas_used - t_gas - 21000
    print(string, gas_used)


@pytest.fixture
def base_state_contract():

    clearing_contract = state.abi_contract(None, path=clearing_contract_path,
                                           language='solidity',
                                           sender=tester.k0,
                                           constructor_parameters=[10**5,
                                                                   "ClearingToken",
                                                                   5, "$$"])

    market_contract = state.abi_contract(None, path=market_contract_path,
                                         language='solidity',
                                         sender=tester.k0,
                                         constructor_parameters=[
                                            encode_hex(clearing_contract.address),
                                            10**5, "Market", 5,
                                            "KWh", 3*60])
    return (clearing_contract, market_contract)


def test_approver(base_state_contract):
    clearing_contract, market_contract = base_state_contract
    assert clearing_contract.getApprover() == encode_hex(A)


def test_globallyApprove(base_state_contract):
    clearing_contract, market_contract = base_state_contract
    assert clearing_contract.globallyApprove(encode_hex(market_contract.address),
                                             1000, sender=A_key)


def test_offer(base_state_contract):
    clearing_contract, market_contract = base_state_contract
    clearing_contract.globallyApprove(encode_hex(market_contract.address),
                                      10000, sender=A_key)
    offer_id = market_contract.offer(7, 956, sender=B_key)
    assert market_contract.getOffer(offer_id) == [7, 956, encode_hex(B)]


def test_offer_fail(base_state_contract):
    clearing_contract, market_contract = base_state_contract
    zero_address = b'0' * 40
    clearing_contract.globallyApprove(encode_hex(market_contract.address),
                                      10000, sender=A_key)
    offer_id = market_contract.offer(0, 956, sender=B_key)
    assert market_contract.getOffer(offer_id) == [0, 0, zero_address]


def test_cancel(base_state_contract):
    clearing_contract, market_contract = base_state_contract
    zero_address = b'0' * 40
    assert clearing_contract.globallyApprove(encode_hex(market_contract.address),
                                             10000, sender=A_key)
    offer_id = market_contract.offer(7, 956, sender=B_key)
    assert market_contract.getOffer(offer_id) == [7, 956, encode_hex(B)]
    assert market_contract.cancel(offer_id, sender=B_key)
    assert market_contract.getOffer(offer_id) == [0, 0, zero_address]


def test_trade(base_state_contract):
    clearing_contract, market_contract = base_state_contract
    assert clearing_contract.globallyApprove(encode_hex(market_contract.address),
                                             10000, sender=A_key)
    offer_id = market_contract.offer(7, 956, sender=B_key)
    assert market_contract.trade(offer_id, sender=C_key)
    assert clearing_contract.balanceOf(C) == -6692
    assert clearing_contract.balanceOf(B) == 6692


def test_seller_trade_fail(base_state_contract):
    """Checks if msg.sender == offer.seller then trade should fail"""
    clearing_contract, market_contract = base_state_contract
    assert clearing_contract.globallyApprove(encode_hex(market_contract.address),
                                             10000, sender=A_key)
    offer_id = market_contract.offer(7, 956, sender=B_key)
    assert not market_contract.trade(offer_id, sender=B_key)


def test_offer_price_negative(base_state_contract):
    """
    Scenario where you need to get rid of your energy and you pay the
    buyer to take your excess energy. Difference is offer price is negative.
    """
    clearing_contract, market_contract = base_state_contract
    assert clearing_contract.globallyApprove(encode_hex(market_contract.address),
                                             10000, sender=A_key)
    buyer, buyer_key, seller, seller_key = B, B_key, C, C_key
    offer_id = market_contract.offer(7, -10, sender=seller_key)
    assert market_contract.trade(offer_id, sender=buyer_key)
    assert clearing_contract.balanceOf(buyer) == 70
    assert clearing_contract.balanceOf(seller) == -70


def test_offer_price_zero(base_state_contract):
    zero_address = b'0' * 40
    clearing_contract, market_contract = base_state_contract
    assert clearing_contract.globallyApprove(encode_hex(market_contract.address),
                                             10000, sender=A_key)
    buyer, buyer_key, seller, seller_key = B, B_key, C, C_key
    offer_id = market_contract.offer(7, 0, sender=seller_key)
    assert market_contract.getOffer(offer_id) == [7, 0, encode_hex(seller)]
    assert market_contract.trade(offer_id, sender=buyer_key)
    assert clearing_contract.balanceOf(buyer) == 0
    assert clearing_contract.balanceOf(seller) == 0
    assert market_contract.getOffer(offer_id) == [0, 0, zero_address]


def test_multiple_markets(base_state_contract):
    clearing_contract, market_contract_a = base_state_contract
    market_contract_b = make_market_contract(tester.k0, [
                            encode_hex(clearing_contract.address),
                            10**5, "Market2", 5,
                            "KWh", 4*60])
    assert encode_hex(market_contract_a.address) != encode_hex(market_contract_b.address)

    assert clearing_contract.globallyApprove(encode_hex(market_contract_a.address),
                                             10000, sender=tester.k0)
    assert clearing_contract.globallyApprove(encode_hex(market_contract_b.address),
                                             20000, sender=tester.k0)
    offerid_a = market_contract_a.offer(8, 790, sender=B_key)
    offerid_b = market_contract_b.offer(9, 899, sender=C_key)
    assert market_contract_a.trade(offerid_a, sender=D_key)
    assert market_contract_b.trade(offerid_b, sender=E_key)
    assert clearing_contract.balanceOf(D) == -6320
    assert clearing_contract.balanceOf(B) == 6320
    assert clearing_contract.balanceOf(E) == -8091
    assert clearing_contract.balanceOf(C) == 8091


def test_trade_fail_afterinterval(base_state_contract):
    clearing_contract, market_contract = base_state_contract
    clearing_contract.globallyApprove(encode_hex(market_contract.address),
                                      10000, sender=A_key)
    offerid_a = market_contract.offer(7, 956, sender=B_key)
    assert market_contract.getOffer(offerid_a) == [7, 956, encode_hex(B)]
    offerid_b = market_contract.offer(8, 799, sender=C_key)
    assert market_contract.getOffer(offerid_b) == [8, 799, encode_hex(C)]
    state.block.timestamp += 2*60
    assert market_contract.trade(offerid_a, sender=D_key)
    assert clearing_contract.balanceOf(D) == -6692
    assert clearing_contract.balanceOf(B) == 6692
    # making block.timestamp more than the interval of the market_contract
    state.block.timestamp += 4*60
    assert not market_contract.trade(offerid_b, sender=E_key)
    assert clearing_contract.balanceOf(C) == 0
    assert clearing_contract.balanceOf(E) == 0


def test_trade_fail_on_marketTransfer_fail(base_state_contract):
    """
    Raises an exception because energy should not be transferred
    if money transaction fails in the trade function
    """
    clearing_contract, market_contract = base_state_contract
    clearing_contract.globallyApprove(encode_hex(market_contract.address),
                                      1000, sender=A_key)
    offer_id = market_contract.offer(7, 956, sender=B_key)
    with pytest.raises(tester.TransactionFailed):
        market_contract.trade(offer_id, sender=C_key)
    assert clearing_contract.balanceOf(B) == 0
    assert clearing_contract.balanceOf(C) == 0
    assert market_contract.balanceOf(B) == 0
    assert market_contract.balanceOf(C) == 0
