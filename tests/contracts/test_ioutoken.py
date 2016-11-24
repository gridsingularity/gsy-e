from contextlib import contextmanager
from ethereum import tester
import ethereum.abi as abi
import pytest, pprint, os

CONTRACT_FN = '../../src/d3a/contracts/IOUToken.sol'


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

@pytest.fixture
def base_state_contract():
    state = tester.state()
    file_dir = os.path.dirname(os.path.realpath('__file__'))
    filename = os.path.join(file_dir, CONTRACT_FN)
    filename = os.path.abspath(os.path.realpath(filename))
    logs = []
    contract = state.abi_contract(None, path=filename,
                                        language='solidity',
                                        sender=tester.k0,
                                        constructor_parameters=[10**5, "Testcoin", 5, "$$"])
    return (state, contract, logs)

def test_balanceOf(base_state_contract):
    state, contract, logs = base_state_contract
    assert contract.balanceOf(A) == 10**5

def test_transfer(base_state_contract):
    state, contract, logs = base_state_contract
    contract.transfer(B, 10000, sender = A_key)
    assert contract.balanceOf(B) == 10000
    assert contract.balanceOf(A) == 90000


def test_transfer_negative_balance(base_state_contract):
    state, contract, logs = base_state_contract
    assert contract.transfer(B, 10000, sender = A_key)
    assert contract.balanceOf(B) == 10000
    contract.transfer(C, 11000, sender = B_key)
    assert contract.balanceOf(B) == -1000
    assert contract.balanceOf(C) == 11000

def test_overflows(base_state_contract):
    state, contract, logs = base_state_contract
    print("Balance of C initial==", contract.balanceOf(C))
    contract.transfer(B, 2**255-1, sender = C_key)
    print("Balance of B after transfer==", contract.balanceOf(B))
    print("Balance of C after transfer==", contract.balanceOf(C))
    contract.transfer(A, 2, sender = C_key)
    print("Balance of C after transfer ==", contract.balanceOf(C))

def test_approve_allowance(base_state_contract):
    state, contract, logs = base_state_contract
    contract.approve(C, 1000, sender = A_key)
    assert contract.allowance(A, C) == 1000

def test_transferFrom(base_state_contract):
    state, contract, logs = base_state_contract
    contract.approve(C, 1000, sender = A_key)
    contract.transferFrom(A, B, 500, sender = C_key)
    assert contract.balanceOf(B) == 500
