import pytest
from web3.contract import Contract
from solc import compile_source
from d3a.util import get_cached_joined_contract_source
from .token_fixtures import blockchain_fixture # NOQA


@pytest.fixture # NOQA
def _bc(blockchain_fixture):
    yield blockchain_fixture


iou_compiled_sol = compile_source(get_cached_joined_contract_source("IOUToken.sol"))
iou_contract_interface = iou_compiled_sol['<stdin>:IOUToken']


@pytest.fixture
def base_state_contract(_bc):
    iou_contract = _bc.eth.contract(abi=iou_contract_interface['abi'],
                                    bytecode=iou_contract_interface['bin'])
    tx_hash = iou_contract.constructor(10**5, "Testcoin", 5, "$$").\
        transact({'from': _bc.eth.accounts[0]})
    iou_address = _bc.eth.waitForTransactionReceipt(tx_hash).contractAddress
    iou_instance = _bc.eth.contract(address=iou_address,
                                    abi=iou_contract_interface['abi'],
                                    ContractFactoryClass=Contract)

    return _bc, iou_instance, iou_address


def test_balanceOf(base_state_contract):
    _bc, iou_contract, iou_address = base_state_contract
    assert iou_contract.functions.balanceOf(_bc.eth.accounts[0]).call() == 10**5


def test_transfer(base_state_contract):
    _bc, iou_contract, iou_address = base_state_contract
    iou_contract.functions.transfer(_bc.eth.accounts[1], 10000).\
        transact({"from": _bc.eth.accounts[0]})
    assert iou_contract.functions.balanceOf(_bc.eth.accounts[1]).call() == 10000
    assert iou_contract.functions.balanceOf(_bc.eth.accounts[0]).call() == 90000


def test_transfer_negative_balance(base_state_contract):
    _bc, iou_contract, iou_address = base_state_contract
    assert iou_contract.functions.transfer(_bc.eth.accounts[1], 10000).\
        transact({"from": _bc.eth.accounts[0]})
    assert iou_contract.functions.balanceOf(_bc.eth.accounts[1]).call() == 10000
    iou_contract.functions.transfer(_bc.eth.accounts[2], 11000).\
        transact({"from": _bc.eth.accounts[1]})
    assert iou_contract.functions.balanceOf(_bc.eth.accounts[1]).call() == -1000
    assert iou_contract.functions.balanceOf(_bc.eth.accounts[2]).call() == 11000


def test_overflows(base_state_contract):
    _bc, iou_contract, iou_address = base_state_contract
    assert iou_contract.functions.balanceOf(_bc.eth.accounts[1]).call() == 0
    assert iou_contract.functions.balanceOf(_bc.eth.accounts[2]).call() == 0
    higher_range = 2**255-1
    lower_range = -2**255
    iou_contract.functions.transfer(_bc.eth.accounts[1], higher_range).\
        transact({"from": _bc.eth.accounts[2]})
    assert iou_contract.functions.balanceOf(_bc.eth.accounts[1]).call() == \
        higher_range  # positive value
    iou_contract.functions.transfer(_bc.eth.accounts[1], 1).\
        transact({"from": _bc.eth.accounts[3]})  # units fold at this point
    assert iou_contract.functions.balanceOf(_bc.eth.accounts[1]).call() == \
        lower_range  # negative value
    assert iou_contract.functions.balanceOf(_bc.eth.accounts[2]).call() == \
        lower_range + 1  # negative value
    iou_contract.functions.transfer(_bc.eth.accounts[0], 2).\
        transact({"from": _bc.eth.accounts[2]})  # units fold at this point
    assert iou_contract.functions.balanceOf(_bc.eth.accounts[2]).call() == \
        higher_range  # positive value


def test_approve_allowance(base_state_contract):
    _bc, iou_contract, iou_address = base_state_contract
    iou_contract.functions.approve(_bc.eth.accounts[2], 1000).\
        transact({"from": _bc.eth.accounts[0]})
    assert iou_contract.functions.allowance(_bc.eth.accounts[0],
                                            _bc.eth.accounts[2]).call() == 1000


def test_transferFrom(base_state_contract):
    _bc, iou_contract, iou_address = base_state_contract
    iou_contract.functions.approve(_bc.eth.accounts[2], 1000).\
        transact({"from": _bc.eth.accounts[0]})
    iou_contract.functions.transferFrom(_bc.eth.accounts[0], _bc.eth.accounts[1], 500).\
        transact({"from": _bc.eth.accounts[2]})
    assert iou_contract.functions.balanceOf(_bc.eth.accounts[1]).call() == 500
