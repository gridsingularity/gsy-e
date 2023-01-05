"""
Copyright 2018 Grid Singularity
This file is part of Grid Singularity Exchange.

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

from logging import getLogger

from gsy_dex.substrate_connection import SubstrateConnection
from gsy_dex.key_manager import KeyManager

log = getLogger(__name__)

NODE_URL = os.environ.get("NODE_URL", "ws://127.0.0.1:9944")


class AccountAreaMapping:
    def __init__(self):
        self.mapping = {}

    def add_area_creds(self, area_uuid, uri):
        self.mapping[area_uuid] = KeyManager.generate_keypair_from_uri(uri)

    def get_area_creds(self, area_uuid):
        self.mapping[area_uuid]

class BcSimulationCommunication:
    def __init__(self):
        self._conn = SubstrateConnection(
            node_url=NODE_URL,
            address_format=42,
            type_registry_preset="substrate-node-template"
        )
        self._mapping = AccountAreaMapping()

    def add_creds_for_area(self, area_uuid, uri):
        self._mapping.add_area_creds(area_uuid, uri)

    def get_creds_from_area(self, area_uuid):
        self._mapping.get_area_creds(area_uuid)

    @property
    def conn(self):
        return self._conn

    @property
    def mapping(self):
        return self._mapping

class AreaWebsocketConnection:
    def __init__(self, bc: BcSimulationCommunication, area_uuid, uri):
        self._conn = bc.conn
        bc.add_creds_for_area(area_uuid, uri)
        self._area_creds = bc.get_creds_from_area(area_uuid)
