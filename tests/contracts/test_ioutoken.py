from contextlib import contextmanager

import pytest
from ethereum import tester

from d3a import get_contract_path

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
    iou_token_path = get_contract_path("IOUToken.sol")
    logs = []
    contract = state.abi_contract(None, path=iou_token_path, language='solidity', sender=tester.k0,
                                  constructor_parameters=[10**5, "Testcoin", 5, "$$"])
    return (state, contract, logs)


def test_balanceOf(base_state_contract):
    state, contract, logs = base_state_contract
    assert contract.balanceOf(A) == 10**5


def test_transfer(base_state_contract):
    state, contract, logs = base_state_contract
    contract.transfer(B, 10000, sender=A_key)
    assert contract.balanceOf(B) == 10000
    assert contract.balanceOf(A) == 90000


def test_transfer_negative_balance(base_state_contract):
    state, contract, logs = base_state_contract
    assert contract.transfer(B, 10000, sender=A_key)
    assert contract.balanceOf(B) == 10000
    contract.transfer(C, 11000, sender=B_key)
    assert contract.balanceOf(B) == -1000
    assert contract.balanceOf(C) == 11000


def test_overflows(base_state_contract):
    state, contract, logs = base_state_contract
    assert contract.balanceOf(B) == 0
    assert contract.balanceOf(C) == 0
    higher_range = 2**255-1
    lower_range = -2**255
    contract.transfer(B, higher_range, sender=C_key)
    assert contract.balanceOf(B) == higher_range  # positive value
    contract.transfer(B, 1, sender=D_key)  # units fold at this point
    assert contract.balanceOf(B) == lower_range  # negative value
    assert contract.balanceOf(C) == lower_range + 1  # negative value
    contract.transfer(A, 2, sender=C_key)  # units fold at this point
    assert contract.balanceOf(C) == higher_range  # positive value


def test_approve_allowance(base_state_contract):
    state, contract, logs = base_state_contract
    contract.approve(C, 1000, sender=A_key)
    assert contract.allowance(A, C) == 1000


def test_transferFrom(base_state_contract):
    state, contract, logs = base_state_contract
    contract.approve(C, 1000, sender=A_key)
    contract.transferFrom(A, B, 500, sender=C_key)
    assert contract.balanceOf(B) == 500
