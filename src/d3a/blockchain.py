from collections import defaultdict, namedtuple
from logging import getLogger
from typing import Dict, List, Mapping, Optional  # noqa
from web3 import Web3, HTTPProvider
from solc import compile_source
from web3.contract import Contract
from subprocess import Popen, DEVNULL
from time import sleep

from d3a.util import get_cached_joined_contract_source
from d3a.models.strategy.const import ConstSettings


log = getLogger(__name__)


User = namedtuple('User', ('name', 'address', 'privkey'))


class BCUsers:
    def __init__(self, chain, contracts, default_balance=10 ** 18):
        self._users = {}
        self._chain = chain
        self._contracts = contracts
        self._default_balance = default_balance

    def __getitem__(self, username_or_addr):
        # from web3 import Web3, HTTPProvider
        # web3 = Web3(HTTPProvider("http://127.0.0.1:8545", request_kwargs={'timeout': 600}))
        self._chain.personal.unlockAccount(self._chain.eth.accounts[0], 'testgsy')

        user = self._users.get(username_or_addr)
        if not user:
            if username_or_addr.startswith("0x"):
                raise KeyError("User with address {} doesn't exist".format(username_or_addr))
            self._users[username_or_addr] = user = self._mk_user(username_or_addr)
            self._users[user.address] = user
            self._chain.eth.waitForTransactionReceipt(
                self._contracts["ClearingToken"].functions
                .globallyApprove(user.address, self._default_balance)
                .transact({"from": self._chain.eth.accounts[0]})
            )
        return user

    def _mk_user(self, username):
        account_address = self._chain.eth.accounts[len(self._users.keys()) + 1]
        return User(username, account_address, None)


class BlockChainInterface:
    def __init__(self, default_user_balance=10 ** 8):
        if ConstSettings.BLOCKCHAIN_START_LOCAL_CHAIN:
            self._ganache_process = Popen(['ganache-cli', '-a', '50', '-e', '10000000000'],
                                          close_fds=False, stdout=DEVNULL, stderr=DEVNULL)
        sleep(2)
        self.chain = Web3(HTTPProvider(ConstSettings.BLOCKCHAIN_URL))
        self.contracts = {}  # type: Dict[str, Contract]
        self.users = BCUsers(self.chain, self.contracts, default_user_balance)
        self.listeners = defaultdict(list)  # type: Dict[str, List[callable]]

    def init_contract(self, contract_filename: str, contract_name: str,
                      args: list, listeners: Optional[List] = None, id_: str = None):

        log.debug("Initializing contract '%s'", contract_name)
        compiled_sol = compile_source(get_cached_joined_contract_source(contract_filename))
        # print("compiled_sol: " + str(compiled_sol))
        contract_interface = compiled_sol['<stdin>:' + contract_name]
        # print("contract_interface: " + str(contract_interface))

        contract = self.chain.eth.contract(abi=contract_interface['abi'],
                                           bytecode=contract_interface['bin'])
        print("contract: " + str(contract))
        print(f'filename {contract_name} {contract_filename}')
        self.chain.personal.unlockAccount(self.chain.eth.accounts[0], 'testgsy')
        tx_hash = contract.constructor(*args).transact({'from': self.chain.eth.accounts[0]})
        contract_address = self.chain.eth.waitForTransactionReceipt(tx_hash).contractAddress
        sleep(1)
        contract = self.chain.eth.contract(address=contract_address,
                                           abi=contract_interface['abi'],
                                           ContractFactoryClass=Contract)

        sleep(5)
        self.contracts[contract.address] = contract
        if id_:
            self.contracts[id_] = contract
        if listeners:
            self.listeners[contract.address].extend(listeners)
        return contract
