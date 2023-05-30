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
import json
import os
import uuid
from ctypes import c_uint32
from logging import getLogger

from gsy_dex.data_classes import Bid, Offer, Trade
from gsy_dex.gsy_collateral import GSyCollateral
from gsy_dex.gsy_orderbook import GSyOrderbook
from gsy_dex.substrate_connection import SubstrateConnection
from gsy_dex.key_manager import KeyManager

from substrateinterface.base import Keypair
from substrateinterface.exceptions import SubstrateRequestException

from gsy_e.gsy_e_core.exceptions import AreaException, SimulationException
from gsy_e.gsy_e_core.redis_connections.area_market import RedisCommunicator

log = getLogger(__name__)

NODE_URL = os.environ.get("NODE_URL", "ws://127.0.0.1:9944")
SUDO_URI = os.environ.get("SUDO_URI", "//Alice")
DEX_TRADES_CHANNEL = os.environ.get("DEX_TRADES_CHANNEL", "dex-trades-events")
DEX_NEW_ORDERS_CHANNEL = os.environ.get("DEX_NEW_ORDERS_CHANNEL", "dex-new-orders-events")


class AccountAreaMapping:
    """
    A class representing account area mapping.

    Attributes:
    - mapping (dict): A dictionary containing the account and its corresponding area.

    Methods:
    - add_area_creds(area_uuid, uri): Adds account credentials for a specific area.
    - get_area_creds(area_uuid): Gets account credentials for a specific area.
    """

    def __init__(self, bc_account_credentials):
        """
        Initializes the AccountAreaMapping class.

        Args:
        - bc_account_credentials (dict): A dictionary containing account credentials.
        """
        self.mapping = bc_account_credentials

    def add_area_creds(self, area_uuid, uri):
        """
        Adds account credentials for a specific area.

        Args:
        - area_uuid (str): The UUID of the area to add credentials for.
        - uri (str): The URI for the account.
        """
        if self.mapping is None:
            self.mapping = {}
        self.mapping[area_uuid] = KeyManager.generate_keypair_from_uri(uri)

    def get_area_creds(self, area_uuid):
        """
        Gets account credentials for a specific area.

        Args:
        - area_uuid (str): The UUID of the area to get credentials for.

        Returns:
        - Keypair: The account credentials for the specified area.
        """
        return self.mapping[area_uuid]


class BcSimulationCommunication:
    """
    A class to handle communication with a substrate-based blockchain node for a simulation.

    Args:
    - bc_account_credentials (dict): A dictionary containing the account credentials for the
     blockchain node.

    Attributes:
    - _conn (SubstrateConnection): A connection to the substrate-based blockchain node.
    - _mapping (AccountAreaMapping): An instance of the AccountAreaMapping class.
    - _sudo_keypair (Keypair): A keypair for a superuser of the blockchain node.
    - gsy_collateral (GSyCollateral): An instance of the GSyCollateral class.
    - gsy_orderbook (GSyOrderbook): An instance of the GSyOrderbook class.
    - registered_address (list): A list of registered user addresses.
    - deposited_collateral (dict): A dictionary containing the amount of collateral deposited
     by each user.
    - trades_buffer (dict): A dictionary containing trade data.
    - redis (RedisCommunicator): An instance of the RedisCommunicator class.
    """

    # pylint: disable=too-many-instance-attributes
    def __init__(self, bc_account_credentials):
        """
        Initializes a BcSimulationCommunication instance.

        Args:
        - bc_account_credentials (dict): A dictionary containing the account credentials
         for the blockchain node.
        """
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
        self.new_bids_buffer = {}
        self.new_offers_buffer = {}
        self.redis = RedisCommunicator()
        self.redis.sub_to_channel(DEX_TRADES_CHANNEL, self.handle_dex_trades_event)
        self.redis.sub_to_channel(DEX_NEW_ORDERS_CHANNEL, self.handle_dex_new_orders_event)
        self.register_matching_engine_operator()

    def add_creds_for_area(self, area_uuid, uri):
        """
        Adds credentials for an area.

        Args:
        - area_uuid (str): The UUID of the area.
        - uri (str): The URI of the user's account.
        """
        self._mapping.add_area_creds(area_uuid, uri)

    @property
    def conn(self):
        """
        Returns the SubstrateConnection instance.

        Returns:
        - SubstrateConnection: The SubstrateConnection instance.
        """
        return self._conn

    def deposit_collateral(self, amount: int, area_uuid: str):
        """
        Deposits collateral into the user's account.

        Args:
        - amount (int): The amount of collateral to deposit.
        - area_uuid (str): The UUID of the area.
        """
        user_keypair = self.get_creds_from_area(area_uuid)
        deposit_collateral_call = self.gsy_collateral.create_deposit_collateral_call(
            amount * 100000)
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
        """
        This method gets the credentials of an area.

        Parameters:
        - area_uuid (str): The UUID of the area.

        Returns:
        - The credentials of the area as returned by the get_area_creds method
         of the Mapping class.
        """
        return self._mapping.get_area_creds(area_uuid)

    @property
    def mapping(self):
        """
        This property returns the instance of the Mapping class.
        """
        return self._mapping

    def pop_trades_from_buffer(self, area_uuid):
        """
        This method removes trades from the trades_buffer for a specific area.

        Parameters:
        - area_uuid (str): The UUID of the area.

        Returns:
        - The trades removed from the trades_buffer for the specified area or None
         if there are no trades in the buffer.
        """
        try:
            return self.trades_buffer.pop(area_uuid, [])
        except KeyError:
            log.error("The %s doesn't have trades in the buffer", area_uuid)
            return None

    def remove_bid_from_buffer(self, area_uuid, order):
        """
        This method removes bid from the new_bids_buffer for a specific area.

        Parameters:
        - area_uuid (str): The UUID of the area.
        - order (Bid): The bid to remove from the buffer.
        """
        try:
            self.new_bids_buffer[area_uuid] = \
                [item for item in self.new_bids_buffer[area_uuid] if item != order]
        except KeyError:
            log.error("The %s doesn't have bids in the buffer", area_uuid)

    def remove_offer_from_buffer(self, area_uuid, order):
        """
        This method removes offer from the new_offers_buffer for a specific area.

        Parameters:
        - area_uuid (str): The UUID of the area.
        - order (Offer): The offer to remove from the buffer.
        """
        try:
            self.new_offers_buffer[area_uuid] = \
                [item for item in self.new_offers_buffer[area_uuid] if item != order]
        except KeyError:
            log.error("The %s doesn't have offers in the buffer", area_uuid)

    def register_matching_engine_operator(self):
        """
        This method registers the sudo as matching engine operator.

        Returns:
        - None.
        """
        if not self._conn.check_sudo_key(self._sudo_keypair):
            log.error(
                "Can't register matching engine operator, the registered keypair: "
                "%s is not a super user",
                self._sudo_keypair.ss58_address)
            return
        register_matching_engine_operator_call = \
            self.gsy_collateral.create_register_matching_engine_operator_call(
                self._sudo_keypair.ss58_address)
        sudo_call = self._conn.create_sudo_call(register_matching_engine_operator_call)
        signed_sudo_call_extrinsic = self._conn.generate_signed_extrinsic(
            sudo_call, self._sudo_keypair)
        try:
            receipt = self._conn.submit_extrinsic(signed_sudo_call_extrinsic)
            if receipt.is_success:
                log.debug("[MATCHING_ENGINE_OPERATOR_REGISTERED][NEW][%s]",
                          self._sudo_keypair.ss58_address)
            else:
                raise AreaException
        except SubstrateRequestException as e:
            log.error("Failed to send the extrinsic to the node %s", e)

    def register_user(self, area_uuid: str):
        """
        This method registers a user in an area.

        Parameters:
        - area_uuid (str): The UUID of the area.

        Returns:
        - None.
        """
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

    def handle_dex_new_orders_event(self, payload):
        """
        This method handles the event when a new orders is made.

        Parameters:
        - payload (dict): A dictionary that contains information about the new orders.

        Returns:
        - None.
        """
        message_json = json.loads(payload["data"])
        new_order_event_json = message_json["payload"]
        log.debug("[NEW ORDER][NEW][%s]", new_order_event_json)
        new_order = new_order_event_json[0]
        if new_order.get("buyer"):
            new_order = Bid.from_serializable_substrate_dict(new_order)
            new_order.nonce = new_order_event_json[1]
            if self.new_bids_buffer.get(str(new_order.area_uuid)):
                self.new_bids_buffer[str(new_order.area_uuid)].append(new_order)
            else:
                self.new_bids_buffer[str(new_order.area_uuid)] = [new_order]
            log.debug("[NEW_BIDS_BUFFER][NEW][%s]", self.new_offers_buffer)
        else:
            new_order = Offer.from_serializable_substrate_dict(new_order)
            new_order.nonce = new_order_event_json[1]
            if self.new_offers_buffer.get(str(new_order.area_uuid)):
                self.new_offers_buffer[str(new_order.area_uuid)].append(new_order)
            else:
                self.new_offers_buffer[str(new_order.area_uuid)] = [new_order]
            log.debug("[NEW_OFFERS_BUFFER][NEW][%s]", self.new_offers_buffer)

    def handle_dex_trades_event(self, payload):
        """
        This method handles the event when a new trade is made.

        Parameters:
        - payload (dict): A dictionary that contains information about the new trade.

        Returns:
        - None.
        """
        message_json = json.loads(payload["data"])
        trade_json = message_json["payload"]
        log.debug("[TRADE][NEW][%s]", trade_json)
        trade = Trade.from_serializable_dict(trade_json)
        if self.trades_buffer.get(str(trade.bid.area_uuid)):
            self.trades_buffer[str(trade.bid.area_uuid)].append(trade)
        else:
            self.trades_buffer[str(trade.bid.area_uuid)] = [trade]
        if self.trades_buffer.get(str(trade.offer.area_uuid)):
            self.trades_buffer[str(trade.offer.area_uuid)].append(trade)
        else:
            self.trades_buffer[str(trade.offer.area_uuid)] = [trade]
        try:
            self.deposited_collateral[str(trade.bid.area_uuid)] -= \
                trade.parameters["selected_energy"] * trade.parameters["energy_rate"]
            self.deposited_collateral[str(trade.offer.area_uuid)] += \
                trade.parameters["selected_energy"] * trade.parameters["energy_rate"]
        except SimulationException as ex:
            log.error(ex)

    def add_sudo_keypair(self, keypair: Keypair):
        """
        Sets the given keypair as sudo keypair for the simulation.

        Args:
        - keypair (Keypair): Keypair to set as sudo keypair.

        Returns:
        - None.
        """
        if not self._conn.check_sudo_key(keypair):
            log.error("Can't add a not super user keypair: %s as sudo", keypair)
            return
        self._sudo_keypair = keypair

    def update_bids(self, bids, area_uuid):
        """
        Update the bids market dict with the bids added to the dex orderbook.

        Args:
        - bids: The bids dict to update
        - area_uuid: The area_uuid to update

        Returns:
        - bids: The updated bids dict
        """
        log.debug("[bids]%s\n[new_bids]%s", bids, self.new_bids_buffer)
        residual_bids = {}
        bc_bids = self.new_bids_buffer.get(str(c_uint32(uuid.UUID(area_uuid).int).value))
        for bc_bid in bc_bids:
            for bid in bids.values():
                if bid.creation_time == \
                        bc_bid.creation_time and \
                        bid.energy == bc_bid.energy and \
                        bid.time_slot == bc_bid.time_slot:
                    log.debug("BID: %s equal to BC_BID: %s", bid, bc_bid)
                    bid.nonce = bc_bid.nonce
                    self.remove_bid_from_buffer(
                        str(c_uint32(uuid.UUID(area_uuid).int).value), bc_bid)
                else:
                    residual_bids[str(uuid.uuid4())] = bc_bid
        return {**bids, **residual_bids}

    def update_offers(self, offers, area_uuid):
        """
        Update the offers market dict with the offers added to the dex orderbook.

        Args:
        - offers: The offers dict to update
        - area_uuid: The area_uuid to update

        Returns:
        - offers: The updated offers dict
        """
        log.debug("[offers]%s\n[new_offers]%s", offers, self.new_offers_buffer)
        residual_offers = {}
        bc_offers = self.new_offers_buffer.get(str(c_uint32(uuid.UUID(area_uuid).int).value))
        for bc_offer in bc_offers:
            for offer in offers.values():
                if offer.creation_time == \
                        bc_offer.creation_time and \
                        offer.energy == bc_offer.energy and \
                        offer.time_slot == bc_offer.time_slot:
                    log.debug("OFFER: %s equal to BC_OFFER: %s", offer, bc_offer)
                    offer.nonce = bc_offer.nonce
                    self.remove_offer_from_buffer(
                        str(c_uint32(uuid.UUID(area_uuid).int).value), bc_offer)
                else:
                    residual_offers[str(uuid.uuid4())] = bc_offer
        return {**offers, **residual_offers}


class AreaWebsocketConnection:
    """
    Class for managing websocket connection to a particular area in a simulation.

    Args:
    - bc (BcSimulationCommunication): Instance of BcSimulationCommunication.
    - area_uuid (str): Unique identifier for the area.
    - uri (str): The URI of the user's account.

    Attributes:
    - _bc (BcSimulationCommunication): Instance of BcSimulationCommunication.
    - _area_creds (Credentials): Credentials for the area.
    """

    def __init__(self, bc: BcSimulationCommunication, area_uuid, uri):
        self._bc = bc
        self._bc.add_creds_for_area(area_uuid, uri)
        self._area_creds = self._bc.get_creds_from_area(area_uuid)

    @property
    def conn(self):
        """Returns the instance of BcSimulationCommunication used for the websocket connection."""
        return self._bc
