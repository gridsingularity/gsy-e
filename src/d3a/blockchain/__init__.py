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

import platform
from d3a_interface.constants_limits import ConstSettings


ENABLE_SUBSTRATE = False

if platform.python_implementation() != "PyPy" and \
        ConstSettings.BlockchainSettings.BC_INSTALLED is True and \
        ENABLE_SUBSTRATE is True:
    from substrateinterface import SubstrateInterface


DEFAULT_SUBSTRATE_URL = "wss://canvas-node.dev.gridsingularity.com/"
TEMPLATE_NODE_ADDRESS_TYPE = 42


class BlockChainInterface:

    def __init__(self):
        self.substrate = SubstrateInterface(
            url=DEFAULT_SUBSTRATE_URL,
            address_type=TEMPLATE_NODE_ADDRESS_TYPE,
            type_registry_preset='canvas'
        )
