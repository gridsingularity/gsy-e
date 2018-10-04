import pytest
import os
from time import sleep
from subprocess import Popen
from web3 import Web3, HTTPProvider
from d3a.models.strategy.const import ConstSettings


def ganachecli_command():
    if "GANACHE_BINARY" in os.environ:
        return os.environ["GANACHE_BINARY"], 5
    else:
        return 'ganache-cli', 2


@pytest.fixture(scope='session')
def blockchain_fixture():
    if ConstSettings.BLOCKCHAIN_START_LOCAL_CHAIN:
        ganachecli, sleep_time = ganachecli_command()
        ganache_subprocess = Popen([ganachecli], close_fds=False)
        sleep(sleep_time)
    else:
        ganache_subprocess = None

    yield Web3(HTTPProvider(ConstSettings.BLOCKCHAIN_URL))

    if ganache_subprocess:
        ganache_subprocess.terminate()
