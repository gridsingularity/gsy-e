from contextlib import contextmanager

import pytest
from time import sleep
import os
from subprocess import Popen
from web3 import Web3, HTTPProvider
from web3.contract import Contract

from solc import compile_source

from d3a.util import get_cached_joined_contract_source
from d3a.models.strategy.const import ConstSettings


iou_compiled_sol = compile_source(get_cached_joined_contract_source("IOUToken.sol"))
iou_contract_interface = iou_compiled_sol['<stdin>:IOUToken']


@contextmanager
def print_gas_used(state, string):
    t_gas = state.block.gas_used
    yield
    gas_used = state.block.gas_used - t_gas - 21000
    print(string, gas_used)


def ganachecli_command():
    if "GANACHE_BINARY" in os.environ:
        return os.environ["GANACHE_BINARY"]
    else:
        return 'ganache-cli'


@pytest.fixture
def base_state_contract():
    ganache_subprocess = Popen([ganachecli_command()], close_fds=False) \
        if ConstSettings.BLOCKCHAIN_START_LOCAL_CHAIN \
        else None
    sleep(5)
    state = Web3(HTTPProvider(ConstSettings.BLOCKCHAIN_URL))

    iou_contract = state.eth.contract(abi=iou_contract_interface['abi'],
                                      bytecode=iou_contract_interface['bin'])
    tx_hash = iou_contract.constructor(10**5, "Testcoin", 5, "$$").\
        transact({'from': state.eth.accounts[0]})
    iou_address = state.eth.waitForTransactionReceipt(tx_hash).contractAddress
    iou_instance = state.eth.contract(address=iou_address,
                                      abi=iou_contract_interface['abi'],
                                      ContractFactoryClass=Contract)

    yield state, iou_instance, iou_address

    if ganache_subprocess:
        ganache_subprocess.terminate()


def test_balanceOf(base_state_contract):
    state, iou_contract, iou_address = base_state_contract
    assert iou_contract.functions.balanceOf(state.eth.accounts[0]).call() == 10**5


def test_transfer(base_state_contract):
    state, iou_contract, iou_address = base_state_contract
    iou_contract.functions.transfer(state.eth.accounts[1], 10000).\
        transact({"from": state.eth.accounts[0]})
    assert iou_contract.functions.balanceOf(state.eth.accounts[1]).call() == 10000
    assert iou_contract.functions.balanceOf(state.eth.accounts[0]).call() == 90000


def test_transfer_negative_balance(base_state_contract):
    state, iou_contract, iou_address = base_state_contract
    assert iou_contract.functions.transfer(state.eth.accounts[1], 10000).\
        transact({"from": state.eth.accounts[0]})
    assert iou_contract.functions.balanceOf(state.eth.accounts[1]).call() == 10000
    iou_contract.functions.transfer(state.eth.accounts[2], 11000).\
        transact({"from": state.eth.accounts[1]})
    assert iou_contract.functions.balanceOf(state.eth.accounts[1]).call() == -1000
    assert iou_contract.functions.balanceOf(state.eth.accounts[2]).call() == 11000


def test_overflows(base_state_contract):
    state, iou_contract, iou_address = base_state_contract
    assert iou_contract.functions.balanceOf(state.eth.accounts[1]).call() == 0
    assert iou_contract.functions.balanceOf(state.eth.accounts[2]).call() == 0
    higher_range = 2**255-1
    lower_range = -2**255
    iou_contract.functions.transfer(state.eth.accounts[1], higher_range).\
        transact({"from": state.eth.accounts[2]})
    assert iou_contract.functions.balanceOf(state.eth.accounts[1]).call() == \
        higher_range  # positive value
    iou_contract.functions.transfer(state.eth.accounts[1], 1).\
        transact({"from": state.eth.accounts[3]})  # units fold at this point
    assert iou_contract.functions.balanceOf(state.eth.accounts[1]).call() == \
        lower_range  # negative value
    assert iou_contract.functions.balanceOf(state.eth.accounts[2]).call() == \
        lower_range + 1  # negative value
    iou_contract.functions.transfer(state.eth.accounts[0], 2).\
        transact({"from": state.eth.accounts[2]})  # units fold at this point
    assert iou_contract.functions.balanceOf(state.eth.accounts[2]).call() == \
        higher_range  # positive value


def test_approve_allowance(base_state_contract):
    state, iou_contract, iou_address = base_state_contract
    iou_contract.functions.approve(state.eth.accounts[2], 1000).\
        transact({"from": state.eth.accounts[0]})
    assert iou_contract.functions.allowance(state.eth.accounts[0],
                                            state.eth.accounts[2]).call() == 1000


def test_transferFrom(base_state_contract):
    state, iou_contract, iou_address = base_state_contract
    iou_contract.functions.approve(state.eth.accounts[2], 1000).\
        transact({"from": state.eth.accounts[0]})
    iou_contract.functions.transferFrom(state.eth.accounts[0], state.eth.accounts[1], 500).\
        transact({"from": state.eth.accounts[2]})
    assert iou_contract.functions.balanceOf(state.eth.accounts[1]).call() == 500
