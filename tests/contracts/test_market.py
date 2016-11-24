from contextlib import contextmanager
from ethereum import tester
import ethereum.abi as abi
import pytest, pprint, os

MARKET_FN = '../../src/d3a/contracts/Market.sol'
LIB_FN = '../../src/d3a/contracts/byte_set_lib.sol'
MONEY_FN = '../../src/d3a/contracts/MoneyIOU.sol'

# setup accounts
accounts = tester.accounts
keys = tester.keys
A, B, C, D, E = accounts[:5]
A_key, B_key, C_key, D_key, E_key = keys[:5]

@contextmanager
def print_gas_used(state, string):
    t_gas = state.block.gas_used
    yield
    gas_used = state.block.gas_used - t_gas - 21000
    print(string, gas_used)


def test_base_state_contract():
    state = tester.state()
    file_dir = os.path.dirname(os.path.realpath('__file__'))
    market_contract_path = os.path.abspath(os.path.realpath(os.path.join(file_dir, MARKET_FN)))
    money_contract_path = os.path.abspath(os.path.realpath(os.path.join(file_dir, MONEY_FN)))
    libcode = open(LIB_FN).read()
    logs = []
    money_contract = state.abi_contract(None, path=money_contract_path,
                                              language='solidity',
                                              sender=tester.k0,
                                              constructor_parameters=[10**5, "Testcoin", 5, "$$"])
