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
import os
from logging import getLogger

from gsy_dex.substrate_connection import SubstrateConnection
from gsy_dex.key_manager import KeyManager

log = getLogger(__name__)

NODE_URL = os.environ.get("NODE_URL", "ws://127.0.0.1:9944")


class AccountAreaMapping:
    def __init__(self, bc_account_credentials):
        self.mapping = bc_account_credentials

    def add_area_creds(self, area_uuid, uri):
        self.mapping[area_uuid] = KeyManager.generate_keypair_from_uri(uri)

    def get_area_creds(self, area_uuid):
        return self.mapping[area_uuid]


class BcSimulationCommunication:
    def __init__(self, bc_account_credentials):
        self._conn = SubstrateConnection(
            node_url=NODE_URL,
            address_format=42,
            type_registry_preset="substrate-node-template"
        )
        self._mapping = AccountAreaMapping(bc_account_credentials)
        self._callback_mapping = {}

    def add_creds_for_area(self, area_uuid, uri):
        self._mapping.add_area_creds(area_uuid, uri)

    def get_creds_from_area(self, area_uuid):
        return self._mapping.get_area_creds(area_uuid)

    def register_market_trade_callback(self, market_id, event_trade_cb):
        self._callback_mapping[market_id] = event_trade_cb

    def unregister_market_trade_callback(self, event_trade_cb):
        pass

    def _receive_bc_event(self, event):
        if event.market_id in self._callback_mapping:
            self._callback_mapping[event.market_id](
                event.accepted_offer, event.residual_offer, event.trade)

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

    def register_market_cb(self, markets: List[MarketBase]):
        for market in markets:
            self._conn.register_market_trade_callback(market.id, market.event_trade)
