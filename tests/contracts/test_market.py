from contextlib import contextmanager
from ethereum import tester
from ethereum.utils import encode_hex
import ethereum.abi as abi
import pytest, pprint, os

MARKET_FN = '../../src/d3a/contracts/Market.sol'
LIB_FN = '../../src/d3a/contracts/byte_set_lib.sol'
MONEY_FN = '../../src/d3a/contracts/MoneyIOU.sol'

# setup accounts
accounts = tester.accounts
keys = tester.keys
A, B, C, D, E, F, G, H= accounts[:8]
A_key, B_key, C_key, D_key, E_key, F_key, G_key, H_key = keys[:8]

# contract paths
file_dir = os.path.dirname(os.path.realpath('__file__'))
market_contract_path = os.path.abspath(os.path.realpath(os.path.join(file_dir, MARKET_FN)))
money_contract_path = os.path.abspath(os.path.realpath(os.path.join(file_dir, MONEY_FN)))
state = tester.state()
def make_market_contract(approver, constructor_params):
    market_contract_path = os.path.abspath(os.path.realpath(os.path.join(file_dir, MARKET_FN)))
    libcode = open(LIB_FN).read()
    set_address = state.contract(libcode, language='solidity', sender=tester.k0)
    return state.abi_contract(None, path=market_contract_path,
                                    language='solidity',
                                    sender=approver,
                                    constructor_parameters = constructor_params,
                                    libraries={'ItSet':encode_hex(set_address)})
@contextmanager
def print_gas_used(state, string):
    t_gas = state.block.gas_used
    yield
    gas_used = state.block.gas_used - t_gas - 21000
    print(string, gas_used)

@pytest.fixture
def base_state_contract():

    libcode = open(LIB_FN).read()
    logs = []
    set_address = state.contract(libcode, language='solidity', sender=tester.k0)
    money_contract = state.abi_contract(None, path=money_contract_path,
                                              language='solidity',
                                              sender=tester.k0,
                                              constructor_parameters=[10**5, "MoneyIOU", 5, "$$"])

    market_contract = state.abi_contract(None, path=market_contract_path,
                                               language='solidity',
                                               sender=tester.k0,
                                               constructor_parameters=[
                                               encode_hex(money_contract.address), 10**5, "Market", 5, "KWh"],
                                               libraries={'ItSet':encode_hex(set_address)})
    return (money_contract, market_contract)

def test_approver(base_state_contract):
    money_contract, market_contract = base_state_contract
    assert money_contract.getApprover() == encode_hex(A)

def test_register_market(base_state_contract):
    money_contract, market_contract = base_state_contract
    assert market_contract.registerMarket(1000, sender = A_key) == True

def test_offer(base_state_contract):
    money_contract, market_contract = base_state_contract
    market_contract.registerMarket(10000, sender = A_key)
    offer_id = market_contract.offer(7, 956, sender = B_key)
    assert market_contract.getOffer(offer_id) == [7, 956, encode_hex(B)]

def test_cancel(base_state_contract):
    money_contract, market_contract = base_state_contract
    zero_address = b'0' * 40
    assert market_contract.registerMarket(10000, sender = A_key) == True
    offer_id = market_contract.offer(7, 956, sender = B_key)
    assert market_contract.getOffer(offer_id) == [7, 956, encode_hex(B)]
    assert market_contract.cancel(offer_id, sender = B_key) == True
    assert market_contract.getOffer(offer_id) == [0, 0, zero_address]

def test_trade(base_state_contract):
    money_contract, market_contract = base_state_contract
    assert market_contract.registerMarket(10000, sender = A_key) == True
    offer_id = market_contract.offer(7, 956, sender = B_key)
    assert market_contract.trade(offer_id, sender = C_key) == True
    assert money_contract.balanceOf(C) == -6692
    assert money_contract.balanceOf(B) == 6692

def test_seller_trade_fail(base_state_contract):
    """Checks if msg.sender == offer.seller then trade should fail"""
    money_contract, market_contract = base_state_contract
    assert market_contract.registerMarket(10000, sender = A_key) == True
    offer_id = market_contract.offer(7, 956, sender = B_key)
    assert market_contract.trade(offer_id, sender = B_key) == False

def test_offer_price_negative(base_state_contract):
    """
    Scenario where you need to get rid of your energy and you pay the
    buyer to take your excess energy. Difference is offer price is negative.
    """
    money_contract, market_contract = base_state_contract
    assert market_contract.registerMarket(10000, sender = A_key) == True
    buyer, buyer_key, seller, seller_key = B, B_key, C, C_key
    offer_id = market_contract.offer(7, -10, sender = seller_key)
    assert market_contract.trade(offer_id, sender = buyer_key) == True
    assert money_contract.balanceOf(buyer) == 70
    assert money_contract.balanceOf(seller) == -70

def test_multiple_markets(base_state_contract):
    money_contract, market_contract_a = base_state_contract
    market_contract_b = make_market_contract(tester.k0, [encode_hex(money_contract.address),
                                                10**5, "Market2", 5, "KWh"])
    assert encode_hex(market_contract_a.address) != encode_hex(market_contract_b.address)
    assert market_contract_a.registerMarket(10000, sender = tester.k0) == True
    assert market_contract_b.registerMarket(20000, sender = tester.k0) == True
    offerid_a = market_contract_a.offer(8, 790, sender = B_key)
    offerid_b = market_contract_b.offer(9, 899, sender = C_key)
    assert market_contract_a.trade(offerid_a, sender = D_key) == True
    assert market_contract_b.trade(offerid_b, sender = E_key) == True
    assert money_contract.balanceOf(D) == -6320
    assert money_contract.balanceOf(B) == 6320
    assert money_contract.balanceOf(E) == -8091
    assert money_contract.balanceOf(C) == 8091
