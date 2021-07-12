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
from d3a.blockchain.constants import ENABLE_SUBSTRATE


if platform.python_implementation() != "PyPy" and \
        ENABLE_SUBSTRATE is True:
    from substrateinterface import SubstrateInterface


DEFAULT_SUBSTRATE_URL = "wss://charlie-node.dev.gridsingularity.com/"
TEMPLATE_NODE_ADDRESS_TYPE = 42

custom_type_registry = {
    "runtime_id": 2000,
    "types": {
        "Address": "MultiAddress",
        "LookupSource": "MultiAddress",
        "Keys": {
            "type": "struct",
            "type_mapping": [
                ["grandpa", "AccountId"],
                ["babe", "AccountId"],
                ["im_online", "AccountId"],
                ["authority_discovery", "AccountId"],
                ["parachains", "AccountId"]
            ]
        },
        "Bid": {
            "type": "struct",
            "type_mapping": [
                ["uuid", "u32"],
                ["max_energy", "u32"],
                ["market_uuid", "Option<Vec<u8>>"],
                ["asset_uuid", "Option<Vec<u8>>"],
                ["time_slot", "Vec<u8>"]
            ]
        },
        "Offer": {
            "type": "struct",
            "type_mapping": [
                ["uuid", "u32"],
                ["max_energy", "u32"],
                ["market_uuid", "Option<Vec<u8>>"],
                ["asset_uuid", "Option<Vec<u8>>"],
                ["energy_type", "Vec<u8>"],
                ["time_slot", "Vec<u8>"]
            ]
        },
        "Match": {
            "type": "struct",
            "type_mapping": [
                ["ids", "u32"],
                ["price", "u32"],
                ["energy", "u32"]
            ]
        }
    }
}


class BlockChainInterface:

    def __init__(self):
        self.substrate = SubstrateInterface(
            url=DEFAULT_SUBSTRATE_URL,
            address_type=TEMPLATE_NODE_ADDRESS_TYPE,
            type_registry_preset='substrate-node-template',
            type_registry=custom_type_registry,
            use_remote_preset=False
        )
