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

def make_market_contract(approver, constructor_params):
    state = tester.state()
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
    state = tester.state()
    libcode = open(LIB_FN).read()
    logs = []
    set_address = state.contract(libcode, language='solidity', sender=tester.k0)
    money_contract = state.abi_contract(None, path=money_contract_path,
                                              language='solidity',
                                              sender=tester.k0,
                                              constructor_parameters=[10**5, "MoneyIOU", 5, "$$"])

    print("Set Adress", encode_hex(set_address))
    market_contract = state.abi_contract(None, path=market_contract_path,
                                               language='solidity',
                                               sender=tester.k0,
                                               constructor_parameters=[
                                               encode_hex(money_contract.address), 10**5, "Market", 5, "KWh"],
                                               libraries={'ItSet':encode_hex(set_address)})
    return (state, money_contract, market_contract)

def test_approver(base_state_contract):
    state, money_contract, market_contract = base_state_contract
    assert money_contract.getApprover() == encode_hex(A)

def test_register_market(base_state_contract):
    state, money_contract, market_contract = base_state_contract
    assert market_contract.registerMarket(1000, sender = A_key) == True

def test_offer(base_state_contract):
    state, money_contract, market_contract = base_state_contract
    market_contract.registerMarket(10000, sender = A_key)
    offer_id = market_contract.offer(7, 956, sender = B_key)
    assert market_contract.getOffer(offer_id) == [7, 956, encode_hex(B)]

def test_cancel(base_state_contract):
    state, money_contract, market_contract = base_state_contract
    zero_address = b'0' * 40
    assert market_contract.registerMarket(10000, sender = A_key) == True
    offer_id = market_contract.offer(7, 956, sender = B_key)
    assert market_contract.getOffer(offer_id) == [7, 956, encode_hex(B)]
    assert market_contract.cancel(offer_id, sender = B_key) == True
    assert market_contract.getOffer(offer_id) == [0, 0, zero_address]

def test_trade(base_state_contract):
    state, money_contract, market_contract = base_state_contract
    assert market_contract.registerMarket(10000, sender = A_key) == True
    offer_id = market_contract.offer(7, 956, sender = B_key)
    assert market_contract.trade(offer_id, sender = C_key) == True
    assert money_contract.balanceOf(C) == -6692

def test_multiple_markets(base_state_contract):
    state, money_contract, market_contract_one = base_state_contract
    market_contract_two = make_market_contract(tester.k0, [encode_hex(money_contract.address),
                                                10**5, "Market2", 0, "KWh"])
    print("Market one ==", encode_hex(market_contract_one.address))
    print("Market two==",encode_hex(market_contract_two.address))
    print(market_contract_one.registerMarket(10000, sender = tester.k0))
    print("Approver==", money_contract.getApprover())
    assert encode_hex(money_contract.address) == market_contract_two.getMoneyIOUAddress()
    # MoneyIOU gets the same address as market two
    print("MoneyIOU ==",market_contract_two.getMoneyIOUAddress())
    # market_contract_two.registerMarket(20000, sender = tester.k0)
    print(money_contract.getApprovedMarkets())
