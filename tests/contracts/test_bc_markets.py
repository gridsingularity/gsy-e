import sys
from contextlib import contextmanager

import pytest
from ethereum.tools import tester
from ethereum.utils import encode_hex

from d3a.util import get_cached_joined_contract_source

# setup accounts
accounts = tester.accounts
keys = tester.keys
A, B, C, D, E, F, G, H = accounts[:8]
A_key, B_key, C_key, D_key, E_key, F_key, G_key, H_key = keys[:8]


# contract paths
market_contract_source = get_cached_joined_contract_source('Market.sol')
clearing_contract_source = get_cached_joined_contract_source('ClearingToken.sol')
emptybytes = b'\x00' * 32


def make_market_contract(state, approver, constructor_params):
    return state.contract(market_contract_source, constructor_params, language='solidity',
                          sender=approver)


@contextmanager
def print_gas_used(state, string):
    t_gas = state.block.gas_used
    yield
    gas_used = state.block.gas_used - t_gas - 21000
    print(string, gas_used)


@pytest.fixture(scope='module')
def state():
    # Hack to make pyethereum use cryptodome instead of pysha3
    sys.modules['sha3'] = ''
    # return tester.Chain()
    from ethereum.config import Env
    env = Env()
    env.config["BLOCK_GAS_LIMIT"] = 8000000
    # env.config["GENESIS_GAS_LIMIT"] = 2 ** 63
    # env.config["GENESIS_DIFFICULTY"] = 1
    # env.config["BLOCK_REWARD"] = 1
    # env.config["NEPHEW_REWARD"] = 1
    from ethereum.genesis_helpers import mk_basic_state
    from ethereum.tools.tester import base_alloc
    from ethereum.state import BLANK_UNCLES_HASH
    return tester.Chain(genesis=mk_basic_state(
                base_alloc,
                header={
                    "number": 0,
                    "gas_limit": 7500000,
                    "timestamp": int(0),
                    "gas_used": 0,
                    "difficulty": 0,
                    "uncles_hash": '0x' + encode_hex(BLANK_UNCLES_HASH)
                },
                env=env
            ),
        )


@pytest.fixture
def base_state_contract(state):
    state.mine()
    clearing_contract = state.contract(
        clearing_contract_source,
        [
            10 ** 5,
            "ClearingToken",
            5,
            "CT"
        ],
        language='solidity',
        sender=tester.k0, startgas=3000000
    )

    market_contract = state.contract(
        market_contract_source,
        [
            encode_hex(clearing_contract.address),
            3 * 60
        ],
        language='solidity',
        sender=tester.k0, startgas=3000000
    )

    return clearing_contract, market_contract


def encode_address(bin_input):
    return '0x{}'.format(encode_hex(bin_input))


def test_approver(base_state_contract):
    clearing_contract, market_contract = base_state_contract
    assert clearing_contract.getApprover() == encode_address(A)


def test_globallyApprove(base_state_contract):
    clearing_contract, market_contract = base_state_contract
    assert clearing_contract.globallyApprove(encode_hex(market_contract.address),
                                             1000, sender=A_key)


def test_offer(base_state_contract):
    clearing_contract, market_contract = base_state_contract
    # clearing_contract.globallyApprove(encode_hex(market_contract.address),
    #                                   10000, sender=A_key)
    offer_id = market_contract.offer(7, 956, sender=B_key)
    assert market_contract.getOffer(offer_id) == [7, 956, encode_address(B)]


def test_offer_fail(base_state_contract):
    clearing_contract, market_contract = base_state_contract
    zero_address = '0x' + '0' * 40
    # clearing_contract.globallyApprove(encode_hex(market_contract.address),
    #                                   10000, sender=A_key)
    offer_id = market_contract.offer(0, 956, sender=B_key)
    assert market_contract.getOffer(offer_id) == [0, 0, zero_address]


def test_cancel(base_state_contract):
    clearing_contract, market_contract = base_state_contract
    zero_address = '0x' + '0' * 40
    # assert clearing_contract.globallyApprove(encode_hex(market_contract.address),
    #                                          10000, sender=A_key)
    offer_id = market_contract.offer(7, 956, sender=B_key)
    assert market_contract.getOffer(offer_id) == [7, 956, encode_address(B)]
    assert market_contract.cancel(offer_id, sender=B_key)
    assert market_contract.getOffer(offer_id) == [0, 0, zero_address]


def test_trade(base_state_contract, state):
    clearing_contract, market_contract = base_state_contract

    # assert clearing_contract.globallyApprove(encode_hex(market_contract.address),
    #                                          10000, sender=A_key)
    offer_id = market_contract.offer(7, 956, sender=B_key, startgas=6000000)
    res = market_contract.trade(offer_id, 7, sender=C_key, startgas=4000000)
    assert res[0]
    assert res[1] == emptybytes
    assert res[2] != emptybytes
    # assert clearing_contract.balanceOf(C) == -6692
    # assert clearing_contract.balanceOf(B) == 6692


def test_partial_trade(base_state_contract):
    clearing_contract, market_contract = base_state_contract
    # assert clearing_contract.globallyApprove(encode_hex(market_contract.address),
    #                                          10000, sender=A_key)
    offer_id = market_contract.offer(7, 956, sender=B_key)
    status, newOfferId, tradeId = market_contract.trade(offer_id, 4, sender=C_key)
    assert status
    assert market_contract.getOffer(newOfferId) == [3, 956, encode_address(B)]
    # assert clearing_contract.balanceOf(C) == -3824
    # assert clearing_contract.balanceOf(B) == 3824
    assert market_contract.balanceOf(C) == 4
    assert market_contract.balanceOf(B) == -4


def test_seller_trade_fail(base_state_contract):
    """Checks if msg.sender == offer.seller then trade should fail"""
    clearing_contract, market_contract = base_state_contract
    # assert clearing_contract.globallyApprove(encode_hex(market_contract.address),
    #                                          10000, sender=A_key)
    offer_id = market_contract.offer(7, 956, sender=B_key)
    assert market_contract.trade(offer_id, 7, sender=B_key) == [False, emptybytes, emptybytes]


def test_offer_price_negative(base_state_contract):
    """
    Scenario where you need to get rid of your energy and you pay the
    buyer to take your excess energy. Difference is offer price is negative.
    """
    clearing_contract, market_contract = base_state_contract
    # assert clearing_contract.globallyApprove(encode_hex(market_contract.address),
    #                                          10000, sender=A_key)
    # buyer, buyer_key, seller, seller_key = B, B_key, C, C_key
    buyer_key, seller_key = B_key, C_key
    offer_id = market_contract.offer(7, -10, sender=seller_key)
    res = market_contract.trade(offer_id, 7, sender=buyer_key)
    assert res[0] is True
    assert res[1] == emptybytes
    assert res[2] != emptybytes
    # assert clearing_contract.balanceOf(buyer) == 70
    # assert clearing_contract.balanceOf(seller) == -70


def test_offer_price_zero(base_state_contract):
    zero_address = '0' * 40
    clearing_contract, market_contract = base_state_contract
    # assert clearing_contract.globallyApprove(encode_hex(market_contract.address),
    #                                          10000, sender=A_key)
    buyer, buyer_key, seller, seller_key = B, B_key, C, C_key
    offer_id = market_contract.offer(7, 0, sender=seller_key)
    assert market_contract.getOffer(offer_id) == [7, 0, encode_address(seller)]
    res = market_contract.trade(offer_id, 7, sender=buyer_key)
    assert res[0] is True
    assert res[1] == emptybytes
    assert res[2] != emptybytes
    # assert clearing_contract.balanceOf(buyer) == 0
    # assert clearing_contract.balanceOf(seller) == 0
    assert market_contract.balanceOf(buyer) == 7
    assert market_contract.balanceOf(seller) == -7
    assert market_contract.getOffer(offer_id) == [0, 0, '0x' + zero_address]


def test_multiple_markets(state, base_state_contract):
    clearing_contract, market_contract_a = base_state_contract
    market_contract_b = make_market_contract(state, tester.k0, [
                            encode_hex(clearing_contract.address),
                            4*60])
    assert encode_hex(market_contract_a.address) != encode_hex(market_contract_b.address)

    # assert clearing_contract.globallyApprove(encode_hex(market_contract_a.address),
    #                                          10000, sender=tester.k0)
    # assert clearing_contract.globallyApprove(encode_hex(market_contract_b.address),
    #                                          20000, sender=tester.k0)
    offerid_a = market_contract_a.offer(8, 790, sender=B_key)
    offerid_b = market_contract_b.offer(9, 899, sender=C_key)
    status_a, newOfferId_a, _ = market_contract_a.trade(offerid_a, 8, sender=D_key)
    status_b, newOfferId_b, _ = market_contract_b.trade(offerid_b, 9, sender=E_key)
    assert status_a, status_b
    assert (newOfferId_a, newOfferId_b) == (emptybytes, emptybytes)
    # assert clearing_contract.balanceOf(D) == -6320
    # assert clearing_contract.balanceOf(B) == 6320
    # assert clearing_contract.balanceOf(E) == -8091
    # assert clearing_contract.balanceOf(C) == 8091


@pytest.mark.skip(reason="depends on the clearing token's correct operation.")
def test_trade_fail_afterinterval(base_state_contract, state):
    clearing_contract, market_contract = base_state_contract
    # clearing_contract.globallyApprove(encode_hex(market_contract.address),
    #                                   10000, sender=A_key)
    offerid_a = market_contract.offer(7, 956, sender=B_key)
    assert market_contract.getOffer(offerid_a) == [7, 956, '0x' + encode_hex(B)]
    offerid_b = market_contract.offer(8, 799, sender=C_key)
    assert market_contract.getOffer(offerid_b) == [8, 799, '0x' + encode_hex(C)]
    state.block.timestamp += 2*60
    res = market_contract.trade(offerid_a, 7, sender=D_key)
    assert res[0] is True
    assert res[1] == emptybytes
    assert res[2] != emptybytes
    # assert clearing_contract.balanceOf(D) == -6692
    # assert clearing_contract.balanceOf(B) == 6692
    # making block.timestamp more than the interval of the market_contract
    state.block.timestamp += 4*60
    res = market_contract.trade(offerid_b, 8, sender=E_key)
    assert res[0] is True
    assert res[1] == emptybytes
    assert res[2] == emptybytes
    # assert clearing_contract.balanceOf(C) == 0
    # assert clearing_contract.balanceOf(E) == 0


@pytest.mark.skip(reason="depends on the clearing token's correct operation.")
def test_trade_fail_on_clearingTransfer_fail(base_state_contract):
    """
    Raises an exception because energy should not be transferred
    if money transaction fails in the trade function
    """
    clearing_contract, market_contract = base_state_contract
    # clearing_contract.globallyApprove(encode_hex(market_contract.address),
    #                                   1000, sender=A_key)
    offer_id = market_contract.offer(7, 956, sender=B_key)
    with pytest.raises(tester.TransactionFailed):
        market_contract.trade(offer_id, 7, sender=C_key)
    # assert clearing_contract.balanceOf(B) == 0
    # assert clearing_contract.balanceOf(C) == 0
    assert market_contract.balanceOf(B) == 0
    assert market_contract.balanceOf(C) == 0
