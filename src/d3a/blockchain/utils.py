from d3a.models.const import ConstSettings
from d3a.d3a_core.util import wait_until_timeout_blocking
from logging import getLogger
import time

log = getLogger(__name__)


def wait_for_node_synchronization(bc_interface):
    if ConstSettings.BlockchainSettings.START_LOCAL_CHAIN:
        return

    node_status = bc_interface.chain.eth.syncing
    current_time = time.time()
    time_out = ConstSettings.BlockchainSettings.TIMEOUT
    while not node_status and (time.time() < (current_time + time_out)):
        node_status = bc_interface.chain.eth.syncing
        if time.time() >= (current_time + time_out):
            raise Exception('Syncing to blockchain failed')
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
