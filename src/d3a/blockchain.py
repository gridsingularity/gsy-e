from collections import namedtuple
from typing import Dict, Mapping  # noqa

import rlp
from ethereum import blocks
from ethereum.tester import ABIContract, state, DEFAULT_ACCOUNT  # noqa
from ethereum.utils import sha3, privtoaddr

from pendulum import Interval, Pendulum  # noqa

from d3a import get_contract_path


User = namedtuple('User', ('name', 'address', 'privkey'))


class BCUsers:
    def __init__(self, state, default_balance=10**24):
        self._users = {}
        self._state = state
        self._default_balance = default_balance

    def __getitem__(self, username):
        user = self._users.get(username)
        if not user:
            self._users[username] = user = self._mk_user(username)
        if not self._state.block.account_exists(user.address):
            self._state.block.set_balance(user.address, self._default_balance)
        return user

    @staticmethod
    def _mk_user(username):
        key = sha3(username)
        user = User(username, privtoaddr(key), key)
        return user


class State(state):
    def __init__(self, time_source: callable):
        super().__init__(0)

        self.time_source = time_source

        # Override defaults
        self.block = blocks.genesis(self.env)
        self.blocks = [self.block]
        self.block.timestamp = time_source().int_timestamp
        self.block.coinbase = DEFAULT_ACCOUNT
        self.block.gas_limit = 10 ** 9

    def mine(self, number_of_blocks=1, coinbase=DEFAULT_ACCOUNT, **kwargs):
        # Override from base to allow control over block time
        for _ in range(number_of_blocks):
            self.block.finalize()
            self.block.commit_state()
            self.db.put(self.block.hash, rlp.encode(self.block))
            block = blocks.Block.init_from_parent(
                self.block,
                coinbase,
                timestamp=self.time_source().int_timestamp,
            )
            self.block = block
            self.blocks.append(self.block)

    def add_listener(self, listener):
        self.block.log_listeners.append(listener)


class BlockChainInterface:
    def __init__(self, time_source: callable, default_user_balance=10 ** 24):
        self.state = State(time_source)
        self.users = BCUsers(self.state, default_user_balance)  # type: Mapping[str, User]
        self.contracts = {}  # type: Dict[str, ABIContract]

    def init_contract(self, id_: str, contract_name: str, args: list, listeners=None):
        self.contracts[id_] = contract = self.state.abi_contract(
            None,
            path=str(get_contract_path(contract_name)),
            language='solidity',
            constructor_parameters=args
        )
        if listeners:
            for listener in listeners:
                self.state.add_listener(listener)
        return contract
