from d3a.models.const import ConstSettings
from d3a.d3a_core.util import wait_until_timeout_blocking
from logging import getLogger
from d3a.d3a_core.exceptions import D3AException

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
        log.info(f"Account: {address})")
        unlock = \
            chain.personal.unlockAccount(address,
                                         ConstSettings.BlockchainSettings.ACCOUNT_PASSWORD)
        log.info(f"Unlocking: {unlock}")
