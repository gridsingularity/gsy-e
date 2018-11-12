from d3a.models.const import ConstSettings
from d3a.d3a_core.util import wait_until_timeout_blocking
from logging import getLogger
from time import sleep

log = getLogger(__name__)


def wait_for_node_synchronization(bc_interface):
    if ConstSettings.BlockchainSettings.START_LOCAL_CHAIN:
        return

    wait_until_timeout_blocking(lambda: bc_interface.chain.eth.syncing is not False, timeout=120)
    highest_block = bc_interface.chain.eth.syncing["highestBlock"]
    wait_until_timeout_blocking(lambda: bc_interface.chain.eth.blockNumber >= highest_block)
    sleep(0.1)


def unlock_account(chain, address):
    if ConstSettings.BlockchainSettings.START_LOCAL_CHAIN:
        return
    else:
        log.info(f"Account: {address})")
        unlock = \
            chain.personal.unlockAccount(address,
                                         ConstSettings.BlockchainSettings.ACCOUNT_PASSWORD)
        log.info(f"Unlocking: {unlock}")
