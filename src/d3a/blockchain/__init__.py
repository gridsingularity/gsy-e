"""
Copyright 2018 Grid Singularity
This file is part of D3A.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

from collections import defaultdict, namedtuple
from logging import getLogger
from typing import Dict, List, Optional  # noqa
from web3 import Web3, HTTPProvider
from solc import compile_source
from web3.contract import Contract
from subprocess import Popen, DEVNULL

from d3a.d3a_core.util import get_cached_joined_contract_source
from d3a.blockchain.users import BCUsers
from d3a.blockchain.utils import unlock_account
from d3a_interface.constants_limits import ConstSettings
from d3a_interface.utils import wait_until_timeout_blocking


log = getLogger(__name__)


User = namedtuple('User', ('name', 'address', 'privkey'))


class BlockChainInterface:
    def __init__(self, default_user_balance=10 ** 8):
        if ConstSettings.BlockchainSettings.START_LOCAL_CHAIN:
            self._ganache_process = Popen(['ganache-cli', '-a', '50', '-e', '10000000000'],
                                          close_fds=False, stdout=DEVNULL, stderr=DEVNULL)
            self.chain = Web3(HTTPProvider(ConstSettings.BlockchainSettings.URL))
            log.debug("Launching Ganache Blockchain")

        else:
            self.chain = Web3(HTTPProvider(ConstSettings.BlockchainSettings.URL))
            log.debug("Connected to Remote Blockchain")

            wait_until_timeout_blocking(lambda: self.chain.net.peerCount > 0, timeout=20)
            log.debug(f"Number of Peers: {self.chain.net.peerCount}")

        self.contracts = {}  # type: Dict[str, Contract]
        self.users = BCUsers(self.chain, self.contracts, default_user_balance)
        self.listeners = defaultdict(list)  # type: Dict[str, List[callable]]
        self.init_contract("ClearingToken.sol", "ClearingToken", [10 ** 10,
                                                                  "ClearingToken", 0,
                                                                  "CT"],
                           id_='ClearingToken')

    def init_contract(self, contract_filename: str, contract_name: str,
                      args: list, listeners: Optional[List] = None, id_: str = None):

        log.trace("Initializing contract '%s'", contract_name)
        compiled_sol = compile_source(get_cached_joined_contract_source(contract_filename))
        contract_interface = compiled_sol['<stdin>:' + contract_name]

        contract = self.chain.eth.contract(abi=contract_interface['abi'],
                                           bytecode=contract_interface['bin'])
        unlock_account(self.chain, self.chain.eth.accounts[0])
        tx_hash = contract.constructor(*args).transact({'from': self.chain.eth.accounts[0]})
        wait_until_timeout_blocking(lambda: self.chain.eth.waitForTransactionReceipt(tx_hash).
                                    contractAddress is not None, timeout=20)
        contract_address = self.chain.eth.waitForTransactionReceipt(tx_hash).contractAddress
        contract = self.chain.eth.contract(address=contract_address,
                                           abi=contract_interface['abi'],
                                           ContractFactoryClass=Contract)
        log.debug(f"{contract_name} SmartContract deployed with Address: {contract_address}")
        self.contracts[contract.address] = contract
        if id_:
            self.contracts[id_] = contract
        if listeners:
            self.listeners[contract.address].extend(listeners)
        return contract
