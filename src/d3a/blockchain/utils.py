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
from d3a_interface.constants_limits import ConstSettings
from d3a.d3a_core.util import wait_until_timeout_blocking
from logging import getLogger
from d3a.d3a_core.exceptions import D3AException
import os
import time

log = getLogger(__name__)


class BlockchainTimeoutException(D3AException):
    pass


def wait_for_node_synchronization(bc_interface):
    if ConstSettings.BlockchainSettings.START_LOCAL_CHAIN:
        return

    node_status = bc_interface.chain.eth.syncing
    current_time = time.time()
    time_out = ConstSettings.BlockchainSettings.TIMEOUT
    while not node_status and (time.time() < (current_time + time_out)):
        node_status = bc_interface.chain.eth.syncing
        if time.time() >= (current_time + time_out):
            raise BlockchainTimeoutException(f"Syncing to blockchain failed after "
                                             f"timeout: {time_out} secs")
    highest_block = node_status["highestBlock"]
    wait_until_timeout_blocking(lambda: bc_interface.chain.eth.blockNumber >= highest_block)
    time.sleep(0.1)


def unlock_account(chain, address):
    if ConstSettings.BlockchainSettings.START_LOCAL_CHAIN:
        return
    else:
        account_pass = os.getenv("BLOCKCHAIN_ACCOUNT_PASSWORD", "testgsy")
        log.debug(f"Account: {address})")
        unlock = \
            chain.personal.unlockAccount(address, account_pass)
        log.debug(f"Unlocking: {unlock}")
