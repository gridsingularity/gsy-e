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
import pytest
import os
from time import sleep
from subprocess import Popen
from web3 import Web3, HTTPProvider
from d3a_interface.constants_limits import ConstSettings


def ganachecli_command():
    if "GANACHE_BINARY" in os.environ:
        return os.environ["GANACHE_BINARY"], 5
    else:
        return 'ganache-cli', 2


@pytest.fixture(scope='session')
def blockchain_fixture():
    if ConstSettings.BlockchainSettings.START_LOCAL_CHAIN:
        ganachecli, sleep_time = ganachecli_command()
        ganache_subprocess = Popen([ganachecli], close_fds=False)
        sleep(sleep_time)
    else:
        ganache_subprocess = None
    yield Web3(HTTPProvider(ConstSettings.BlockchainSettings.URL))

    if ganache_subprocess:
        ganache_subprocess.terminate()
