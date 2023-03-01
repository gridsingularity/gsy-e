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
# pylint: skip-file
import json
import os
from logging import getLogger

from gsy_dex.data_classes import Trade
from gsy_dex.gsy_collateral import GSyCollateral
from gsy_dex.gsy_orderbook import GSyOrderbook
from gsy_dex.substrate_connection import SubstrateConnection
from gsy_dex.key_manager import KeyManager

from substrateinterface.base import Keypair
from substrateinterface.exceptions import SubstrateRequestException

from gsy_e.gsy_e_core.exceptions import AreaException
from gsy_e.gsy_e_core.redis_connections.area_market import RedisCommunicator

log = getLogger(__name__)

NODE_URL = os.environ.get("NODE_URL", "ws://127.0.0.1:9944")
SUDO_URI = os.environ.get("SUDO_URI", "//Alice")
DEX_TRADES_CHANNEL = os.environ.get("DEX_TRADES_CHANNEL", "dex-trades-events")


class AccountAreaMapping:
    def __init__(self, bc_account_credentials):
        self.mapping = bc_account_credentials

    def add_area_creds(self, area_uuid, uri):
        self.mapping[area_uuid] = KeyManager.generate_keypair_from_uri(uri)

    def get_area_creds(self, area_uuid):
        return self.mapping[area_uuid]


class BcSimulationCommunication:
    # pylint: disable=too-many-instance-attributes
    def __init__(self, bc_account_credentials):
        self._conn = SubstrateConnection(
            node_url=NODE_URL,
            address_format=42,
            type_registry_preset="substrate-node-template"
        )
        self._mapping = AccountAreaMapping(bc_account_credentials)
        self._sudo_keypair = KeyManager.generate_keypair_from_uri(SUDO_URI)
        self.gsy_collateral = GSyCollateral(self._conn.substrate)
        self.gsy_orderbook = GSyOrderbook(self._conn.substrate)
        self.registered_address = []
        self.deposited_collateral = {}
        self.trades_buffer = {}
        self.redis = RedisCommunicator()
        self.redis.sub_to_channel(DEX_TRADES_CHANNEL, self.handle_dex_trades_event)

    def add_creds_for_area(self, area_uuid, uri):
        self._mapping.add_area_creds(area_uuid, uri)

    @property
    def conn(self):
        return self._conn

    def deposit_collateral(self, amount: int, area_uuid: str):
        user_keypair = self.get_creds_from_area(area_uuid)
        deposit_collateral_call = self.gsy_collateral.create_deposit_collateral_call(
            amount * 1000000)
        signed_deposit_collateral_call = self._conn.generate_signed_extrinsic(
            deposit_collateral_call, user_keypair)
        try:
            receipt = self._conn.submit_extrinsic(signed_deposit_collateral_call)
            if receipt.is_success:
                log.debug("[COLLATERAL_DEPOSITED][NEW][%s][%s][%s]",
                          amount, area_uuid, user_keypair.ss58_address)
                if area_uuid not in self.deposited_collateral:
                    self.deposited_collateral[area_uuid] = amount
                else:
                    self.deposited_collateral[area_uuid] += amount
            else:
                raise AreaException
        except SubstrateRequestException as e:
            log.error("Failed to send the extrinsic to the node %s", e)

    def get_creds_from_area(self, area_uuid):
        return self._mapping.get_area_creds(area_uuid)

    @property
    def mapping(self):
        return self._mapping

    def pop_trades_from_buffer(self, area_uuid):
        try:
            return self.trades_buffer.pop(area_uuid, [])
        except KeyError:
            log.error("The %s doesn't have trades in the buffer", area_uuid)
            return None

    def register_user(self, area_uuid: str):
        user_address = self.get_creds_from_area(area_uuid).ss58_address
        if user_address not in self.registered_address:
            if not self._conn.check_sudo_key(self._sudo_keypair):
                log.error(
                    "Can't register user, the registered keypair: %s is not a super user",
                    self._sudo_keypair)
                return
            register_user_call = self.gsy_collateral.create_register_user_call(user_address)
            sudo_call = self._conn.create_sudo_call(register_user_call)
            signed_sudo_call_extrinsic = self._conn.generate_signed_extrinsic(
                sudo_call, self._sudo_keypair)
            try:
                receipt = self._conn.submit_extrinsic(signed_sudo_call_extrinsic)
                if receipt.is_success:
                    log.debug("[USER_REGISTERED][NEW][%s][%s]", area_uuid, user_address)
                    self.registered_address.append(user_address)
                else:
                    raise AreaException
            except SubstrateRequestException as e:
                log.error("Failed to send the extrinsic to the node %s", e)

    def handle_dex_trades_event(self, payload):
        message_json = json.loads(payload["data"])
        trade_json = message_json["payload"]
        log.info("[TRADE][NEW][%s]", trade_json)
        trade = Trade.from_serializable_dict(trade_json)
        if self.trades_buffer.get(str(trade.bid.area_uuid)):
            self.trades_buffer[str(trade.bid.area_uuid)].append(trade)
        else:
            self.trades_buffer[str(trade.bid.area_uuid)] = [trade]
        if self.trades_buffer.get(str(trade.offer.area_uuid)):
            self.trades_buffer[str(trade.offer.area_uuid)].append(trade)
        else:
            self.trades_buffer[str(trade.offer.area_uuid)] = [trade]

    def add_sudo_keypair(self, keypair: Keypair):
        if not self._conn.check_sudo_key(keypair):
            log.error("Can't add a not super user keypair: %s as sudo", keypair)
            return
        self._sudo_keypair = keypair


class AreaWebsocketConnection:
    def __init__(self, bc: BcSimulationCommunication, area_uuid, uri):
        self._bc = bc
        self._bc.add_creds_for_area(area_uuid, uri)
        self._area_creds = self._bc.get_creds_from_area(area_uuid)

    @property
    def conn(self):
        return self._bc
