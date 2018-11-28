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
from collections import namedtuple
from logging import getLogger
from d3a.blockchain.utils import unlock_account


log = getLogger(__name__)


User = namedtuple('User', ('name', 'address', 'privkey'))


class BCUsers:
    def __init__(self, chain, contracts, default_balance=10 ** 18):
        self._users = {}
        self._chain = chain
        self._contracts = contracts
        self._default_balance = default_balance

    def __getitem__(self, username_or_addr):
        unlock_account(self._chain, self._chain.eth.accounts[0])

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
        log.info(f"User Name: {username} | Eth Address: {account_address}")
        return User(username, account_address, None)
