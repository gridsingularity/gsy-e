from d3a.models.const import ConstSettings
from logging import getLogger
from time import sleep


log = getLogger(__name__)


BC_NUM_FACTOR = 10 ** 10


def wait_for_node_synchronization(bc_interface):
    if ConstSettings.BlockchainSettings.START_LOCAL_CHAIN:
        return

    node_status = bc_interface.chain.eth.syncing
    while not node_status:
        node_status = bc_interface.chain.eth.syncing
    else:
        highest_block = node_status["highestBlock"]
        while bc_interface.chain.eth.blockNumber < highest_block:
            pass
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
