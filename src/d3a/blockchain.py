from collections import defaultdict, namedtuple
from functools import partial
from logging import getLogger
from typing import Dict, List, Mapping, Optional  # noqa

from ethereum.common import mk_block_from_prevstate, set_execution_results
from ethereum.consensus_strategy import get_consensus_strategy
from ethereum.genesis_helpers import mk_basic_state
from ethereum.meta import make_head_candidate
from ethereum.pow import chain
from ethereum.pow.ethpow import Miner
from ethereum.state import BLANK_UNCLES_HASH
from ethereum.tools.tester import ABIContract, Chain as BaseChain, a0, base_alloc, k0
from ethereum.utils import encode_hex, privtoaddr, sha3

from d3a.util import get_cached_joined_contract_source


log = getLogger(__name__)


User = namedtuple('User', ('name', 'address', 'privkey'))


class BCUsers:
    def __init__(self, chain: "Chain", default_balance=10 ** 8):
        self._users = {}
        self._chain = chain
        self._default_balance = default_balance

    def __getitem__(self, username_or_addr):
        user = self._users.get(username_or_addr)
        if not user:
            if username_or_addr.startswith("0x"):
                raise KeyError("User with address {} doesn't exist".format(username_or_addr))
            self._users[username_or_addr] = user = self._mk_user(username_or_addr)
            self._users[user.address] = user
        if not self._chain.head_state.account_exists(user.address):
            self._chain.tx(k0, user.address, self._default_balance)
        return user

    @staticmethod
    def _mk_user(username):
        key = sha3(username)
        user = User(username, privtoaddr(key), key)
        return user


class Chain(BaseChain):
    def __init__(self, time_source):
        self.time_source = time_source
        self.chain = chain.Chain(
            genesis=mk_basic_state(
                base_alloc,
                header={
                    "number": 0,
                    "gas_limit": 10 ** 10,
                    "gas_used": 0,
                    "timestamp": self.time_source().int_timestamp - 1,
                    "difficulty": 1,
                    "uncles_hash": '0x' + encode_hex(BLANK_UNCLES_HASH)
                }),
            reset_genesis=True
        )
        self.cs = get_consensus_strategy(self.chain.env.config)
        self.block = mk_block_from_prevstate(self.chain, timestamp=self.chain.state.timestamp + 1)
        self.head_state = self.chain.state.ephemeral_clone()
        self.cs.initialize(self.head_state, self.block)
        self.last_sender = None
        self.last_tx = None

    def mine(self, number_of_blocks=1, coinbase=a0):
        listeners = self.head_state.log_listeners

        self.cs.finalize(self.head_state, self.block)
        set_execution_results(self.head_state, self.block)
        self.block = Miner(self.block).mine(rounds=100, start_nonce=0)
        assert self.chain.add_block(self.block)
        assert self.head_state.trie.root_hash == self.chain.state.trie.root_hash
        for i in range(1, number_of_blocks):
            b, _ = make_head_candidate(self.chain, timestamp=self.time_source().int_timestamp)
            b = Miner(b).mine(rounds=100, start_nonce=0)
            assert self.chain.add_block(b)
        self.block = mk_block_from_prevstate(self.chain,
                                             timestamp=self.time_source().int_timestamp)
        self.head_state = self.chain.state.ephemeral_clone()
        self.cs.initialize(self.head_state, self.block)

        self.head_state.log_listeners = listeners

    def add_listener(self, listener):
        self.head_state.log_listeners.append(listener)


class BlockChainInterface:
    def __init__(self, time_source: callable, delay_listeners=True, default_user_balance=10 ** 8):
        self.chain = Chain(time_source)
        self.chain.add_listener(self._listener_proxy)
        self.users = BCUsers(self.chain, default_user_balance)  # type: Mapping[str, User]
        self.contracts = {}  # type: Dict[str, ABIContract]
        self.listeners = defaultdict(list)  # type: Dict[str, List[callable]]
        self.delay_listeners = delay_listeners
        self.delayed_listeners = []

    def _listener_proxy(self, log_):
        """Translate raw `Log` instances into dict repr before calling the target listener"""
        for listener in self.listeners[log_.address]:
            event_data = self.contracts[log_.address].translator.listen(log_)
            if self.delay_listeners:
                self.delayed_listeners.append(
                    partial(listener, event_data))
            else:
                listener(event_data)

    def init_contract(self, contract_name: str, args: list, listeners: Optional[List] = None,
                      id_: str = None) -> ABIContract:
        log.debug("Initializing contract '%s'", contract_name)
        contract = self.chain.contract(
            get_cached_joined_contract_source(contract_name),
            args,
            language='solidity',
        )
        self.contracts[contract.address] = contract
        if id_:
            self.contracts[id_] = contract
        if listeners:
            self.listeners[contract.address].extend(listeners)
        return contract

    def fire_delayed_listeners(self):
        if not self.delay_listeners:
            return
        while self.delayed_listeners:
            delayed_listener = self.delayed_listeners.pop()
            delayed_listener()
        self.delayed_listeners = []
