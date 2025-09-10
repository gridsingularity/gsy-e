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
import logging
from collections import deque, namedtuple
from typing import TYPE_CHECKING, Callable, Dict, List, Optional, Tuple

from gsy_framework.data_classes import Trade
from gsy_framework.utils import str_to_pendulum_datetime
from gsy_framework.redis_channels import ExternalStrategyChannels
from pendulum import DateTime
from redis import RedisError

import gsy_e.constants
from gsy_e.gsy_e_core.exceptions import GSyException, MarketException
from gsy_e.gsy_e_core.global_objects_singleton import global_objects
from gsy_e.gsy_e_core.redis_connections.area_market import (
    ExternalConnectionCommunicator,
    ResettableCommunicator,
)
from gsy_e.gsy_e_core.util import get_market_maker_rate_from_config, is_two_sided_market_simulation
from gsy_e.models.market import MarketBase
from gsy_e.models.strategy.external_strategies.dof_filter import DegreesOfFreedomFilter
from gsy_e.models.strategy.future.strategy import FutureMarketStrategyInterface

if TYPE_CHECKING:
    from gsy_e.models.area import Area


IncomingRequest = namedtuple("IncomingRequest", ("request_type", "arguments", "response_channel"))


class CommandTypeNotSupported(Exception):
    """Exception raised when a unsupported command is received."""


class OrderCanNotBePosted(Exception):
    """Exception raised when an order can not be posted."""


class ExternalStrategyConnectionManager:
    """Manage the area's strategy external communication."""

    @staticmethod
    def check_for_connected_and_reply(
        redis: ResettableCommunicator, channel_name: str, is_connected: bool
    ) -> bool:
        """Return whether the external client is registered to access the area.

        Side effect: Publish an error message to client if it isn't registered is_connected: False

        Args:
            redis: Redis communicator that will be used to publish the error message
            channel_name: Channel that the error message will be published to
            is_connected: Indicate whether the client is allowed to act on behalf of the asset
        """
        if not is_connected:
            redis.publish_json(
                channel_name,
                {
                    "status": "error",
                    "error_message": "Client should be registered in order to access this area.",
                },
            )
            return False
        return True

    @staticmethod
    def register(
        redis: ResettableCommunicator,
        response_channel: str,
        is_connected: bool,
        transaction_id: str,
        area_uuid: str,
    ) -> bool:
        """Register the client to act on behalf of an asset and return the status.

        Side effects:
            - Publish a success message to the client
            - Log the error traceback if registration failed
        """
        if is_connected:
            return True
        try:
            redis.publish_json(
                response_channel,
                {
                    "command": "register",
                    "status": "ready",
                    "registered": True,
                    "transaction_id": transaction_id,
                    "device_uuid": area_uuid,
                },
            )
            return True
        except RedisError:
            logging.exception("Error when registering to area %s", response_channel)
        return False

    @staticmethod
    def unregister(
        redis: ResettableCommunicator,
        response_channel: str,
        is_connected: bool,
        transaction_id: str,
    ) -> bool:
        """Unregister the client to deny future actions on behalf of an asset + return the status.

        Side effects:
            - Publish a success message to the client
            - Log the error traceback if un-registration failed
        """
        if not ExternalStrategyConnectionManager.check_for_connected_and_reply(
            redis, response_channel, is_connected
        ):
            return False
        try:
            redis.publish_json(
                response_channel,
                {
                    "command": "unregister",
                    "status": "ready",
                    "unregistered": True,
                    "transaction_id": transaction_id,
                },
            )
            return False
        except RedisError:
            logging.exception("Error when registering to area %s", response_channel)
            return is_connected


class ExternalMixin:
    """Mixin to enable external connection for strategies.

    Although that the direct device connection is disabled (only aggregators can connect),
    we still have the remnants functionality of when we used to have this feature.
    """

    # Due to the dependencies of these mixins (they need to have more precedence in the MRO than
    # the strategy class methods in order to override them) this class cannot be abstract, because
    # it would expose unimplemented abstract methods to the concrete class. Therefore the best
    # alternative is to include here the mixed-in class dependencies as type annotations
    area: "Area"
    owner: "Area"
    spot_market: "MarketBase"
    deactivate: Callable
    event_activate: Callable
    get_state: Callable
    restore_state: Callable
    energy_traded: Callable
    energy_traded_costs: Callable

    def __init__(self, *args, **kwargs):
        self._is_registered: bool = False  # The client asked to get connected
        self.connected: bool = False  # The client is successfully connected to the asset

        # Indefinite flag to ignore external and overridden behaviors and resort to the template's
        self._use_template_strategy: bool = False

        super().__init__(*args, **kwargs)
        self.pending_requests: deque = deque()
        self.channel_names = None

    def event_activate(self, **kwargs):
        """Initiate channel names"""
        super().event_activate(**kwargs)
        self.channel_names = ExternalStrategyChannels(
            gsy_e.constants.EXTERNAL_CONNECTION_WEB,
            gsy_e.constants.CONFIGURATION_ID,
            asset_uuid=self.device.uuid,
            asset_name=self.device.name,
        )

    def _create_future_market_strategy(self):
        """
        Disable future market template strategy in order to leave this respsonsibility
        to the client. This is achieved by overwriting BaseStrategy._create_future_market_strategy.
        """
        return FutureMarketStrategyInterface()

    def get_state(self) -> Dict:
        """Get the state of the asset/market."""
        strategy_state = super().get_state()
        strategy_state.update(
            {"connected": self.connected, "use_template_strategy": self._use_template_strategy}
        )
        return strategy_state

    def restore_state(self, state_dict: Dict) -> None:
        """Restore the state, this is needed when resuming a paused or interrupted simulation."""
        super().restore_state(state_dict)
        self._is_registered = state_dict.get("connected", False)
        self.connected = state_dict.get("connected", False)
        self._use_template_strategy = state_dict.get("use_template_strategy", False)

    @property
    def channel_dict(self) -> Dict:
        """Common API interfaces for all external assets/markets."""
        return {
            self.channel_names.register: self._register,
            self.channel_names.unregister: self._unregister,
            self.channel_names.device_info: self._device_info,
        }

    @property
    def is_aggregator_controlled(self) -> bool:
        """Return whether an aggregator is connected and acting on behalf of the asset/market."""
        return self.redis.aggregator is not None and self.redis.aggregator.is_controlling_device(
            self.device.uuid
        )

    @property
    def should_use_default_strategy(self) -> bool:
        """
        Definite (decisive) flag to ignore external/ overridden behaviors and
        resort to the template's default strategy.
        """
        return self._use_template_strategy or not (self.connected or self.is_aggregator_controlled)

    @staticmethod
    def _get_transaction_id(payload: Dict) -> str:
        """Extract the transaction_id from the received payload."""
        data = json.loads(payload["data"])
        if data.get("transaction_id"):
            return data["transaction_id"]
        raise ValueError("transaction_id not in payload or None")

    def area_reconfigure_event(self, *args, **kwargs) -> None:
        """Reconfigure the device properties at runtime using the provided arguments."""
        if kwargs.get("allow_external_connection"):
            self._use_template_strategy = not kwargs["allow_external_connection"]
        super().area_reconfigure_event(*args, **kwargs)

    def _register(self, payload: Dict) -> None:
        """Callback for the register redis command."""
        self._is_registered = ExternalStrategyConnectionManager.register(
            self.redis,
            self.channel_names.register_response,
            self.connected,
            self._get_transaction_id(payload),
            area_uuid=self.device.uuid,
        )

    def _unregister(self, payload: Dict) -> None:
        """Callback for the unregister redis command."""
        self._is_registered = ExternalStrategyConnectionManager.unregister(
            self.redis,
            self.channel_names.unregister_response,
            self.connected,
            self._get_transaction_id(payload),
        )

    def _update_connection_status(self) -> None:
        """Update the connected flag to sync it with the _registered flag.

        Change assets' connection status including the connection to the aggregator.
        """
        if self.connected and not self._is_registered:
            self.redis.aggregator.device_aggregator_mapping.pop(self.device.uuid, None)
        self.connected = self._is_registered

    def _device_info(self, payload: Dict) -> None:
        """Callback for the device info redis command.

        Return the selected asset info and stats.
        """
        if not ExternalStrategyConnectionManager.check_for_connected_and_reply(
            self.redis, self.channel_names.device_info_response, self.connected
        ):
            return
        arguments = json.loads(payload["data"])
        self.pending_requests.append(
            IncomingRequest("device_info", arguments, self.channel_names.device_info_response)
        )

    def _device_info_impl(self, arguments: Dict, response_channel: str) -> None:
        """Implementation for the _device_info callback, publish this device info/stats."""
        try:
            response = {
                "command": "device_info",
                "status": "ready",
                "device_info": self._device_info_dict,
                "transaction_id": arguments.get("transaction_id"),
            }
        except GSyException:
            error_message = f"Error when handling device info on area {self.device.name}"
            logging.exception(error_message)
            response = {
                "command": "device_info",
                "status": "error",
                "error_message": error_message,
                "transaction_id": arguments.get("transaction_id"),
            }
        self.redis.publish_json(response_channel, response)

    def _device_info_aggregator(self, arguments: Dict) -> Dict:
        """Callback for the device_info endpoint when sent by aggregator.

        Return this device info.
        """
        try:
            response = {
                "command": "device_info",
                "status": "ready",
                "device_info": self._device_info_dict,
                "transaction_id": arguments.get("transaction_id"),
                "area_uuid": self.device.uuid,
            }
        except GSyException:
            response = {
                "command": "device_info",
                "status": "error",
                "error_message": f"Error when handling device info on area {self.device.name}.",
                "transaction_id": arguments.get("transaction_id"),
                "area_uuid": self.device.uuid,
            }
        return response

    def _get_market_from_command_argument(self, arguments: Dict) -> MarketBase:
        """Extract the time_slot from command argument and return the needed market."""
        if arguments.get("time_slot") is None:
            return self.spot_market
        time_slot = str_to_pendulum_datetime(arguments["time_slot"])
        return self._get_market_from_time_slot(time_slot)

    def _get_time_slot_from_external_arguments(self, arguments: Dict) -> Optional[DateTime]:
        if arguments.get("time_slot"):
            return str_to_pendulum_datetime(arguments["time_slot"])
        return None

    def _get_market_from_time_slot(self, time_slot: DateTime) -> MarketBase:
        """Get the market instance based on the time_slot."""
        market = self.area.get_market(time_slot)

        market = market or self.area.get_settlement_market(time_slot)

        if not market and time_slot in self.area.future_market_time_slots:
            market = self.area.future_markets
        if not market:
            raise MarketException(
                f"Timeslot {time_slot} is not currently in the spot, future or "
                f"settlement markets"
            )
        return market

    def _offer_aggregator_impl(
        self, arguments: Dict, market: "MarketBase", time_slot: DateTime, available_energy: float
    ) -> Dict:
        """Post offer in the market for aggregator connection to load or PV."""
        response_message = ""
        arguments, filtered_fields = self.filter_degrees_of_freedom_arguments(arguments)
        if filtered_fields:
            response_message = (
                "The following arguments are not supported for this market and have been "
                f"removed from your order: {filtered_fields}."
            )

        required_args = {"price", "energy", "type", "transaction_id"}
        allowed_args = required_args.union({"replace_existing", "time_slot"})
        try:
            # Check that all required arguments have been provided
            assert all(arg in arguments.keys() for arg in required_args)
            # Check that every provided argument is allowed
            assert all(arg in allowed_args for arg in arguments.keys())

            replace_existing = arguments.pop("replace_existing", True)

            if not self.can_offer_be_posted(
                arguments["energy"],
                arguments["price"],
                available_energy,
                market,
                time_slot=time_slot,
                replace_existing=replace_existing,
            ):
                raise OrderCanNotBePosted

            offer_arguments = {
                k: v for k, v in arguments.items() if k not in ["transaction_id", "type"]
            }

            offer = self.post_offer(market, replace_existing=replace_existing, **offer_arguments)
            response = {
                "command": "offer",
                "status": "ready",
                "offer": offer.to_json_string(),
                "transaction_id": arguments.get("transaction_id"),
                "area_uuid": self.device.uuid,
                "market_type": market.type_name,
                "message": response_message,
            }
        except (OrderCanNotBePosted, GSyException) as ex:
            if isinstance(ex, OrderCanNotBePosted):
                # This can happen in the normal flow, when the user sends an incorrect offer
                logging.info("Error when handling offer on area %s. %s", self.device.name, ex)
            else:
                # This is more unexpected and we might want to be notified
                logging.exception("Error when handling offer on area %s. %s", self.device.name, ex)

            response = {
                "command": "offer",
                "status": "error",
                "market_type": market.type_name,
                "error_message": "Error when handling offer create "
                f"on area {self.device.name} with arguments {arguments}.",
                "area_uuid": self.device.uuid,
                "transaction_id": arguments.get("transaction_id"),
            }
        return response

    def _bid_aggregator_impl(
        self, arguments: Dict, market: "MarketBase", time_slot: DateTime, required_energy: float
    ) -> Dict:
        """Post bid in the market for aggregator connection to load or PV."""
        response_message = ""
        arguments, filtered_fields = self.filter_degrees_of_freedom_arguments(arguments)
        if filtered_fields:
            response_message = (
                "The following arguments are not supported for this market and have been "
                f"removed from your order: {filtered_fields}."
            )

        required_args = {"price", "energy", "type", "transaction_id"}
        allowed_args = required_args.union({"replace_existing", "time_slot"})

        try:
            # Check that all required arguments have been provided
            assert all(arg in arguments.keys() for arg in required_args)
            # Check that every provided argument is allowed
            assert all(arg in allowed_args for arg in arguments.keys())

            replace_existing = arguments.pop("replace_existing", True)
            if not self.can_bid_be_posted(
                arguments["energy"],
                arguments["price"],
                required_energy,
                market,
                time_slot=time_slot,
                replace_existing=replace_existing,
            ):
                raise OrderCanNotBePosted
            bid = self.post_bid(
                market,
                arguments["price"],
                arguments["energy"],
                replace_existing=replace_existing,
                time_slot=time_slot,
            )
            response = {
                "command": "bid",
                "status": "ready",
                "bid": bid.to_json_string(),
                "area_uuid": self.device.uuid,
                "transaction_id": arguments.get("transaction_id"),
                "market_type": market.type_name,
                "message": response_message,
            }
        except (OrderCanNotBePosted, GSyException) as ex:
            if isinstance(ex, OrderCanNotBePosted):
                # This can happen in the normal flow, when the user sends an incorrect bid
                logging.info("Error when handling bid on area %s. %s", self.device.name, ex)
            else:
                # This is more unexpected and we might want to be notified
                logging.exception("Error when handling bid on area %s. %s", self.device.name, ex)

            response = {
                "command": "bid",
                "status": "error",
                "area_uuid": self.device.uuid,
                "market_type": market.type_name,
                "error_message": "Error when handling bid create "
                f"on area {self.device.name} with arguments {arguments}.",
                "transaction_id": arguments.get("transaction_id"),
            }
        return response

    @property
    def device(self) -> "Area":
        """Return the asset/market area instance that owns this strategy."""
        return self.owner

    @property
    def redis(self) -> "ExternalConnectionCommunicator":
        """Return the external_redis_communicator of the owner config instance."""
        return self.owner.config.external_redis_communicator

    @property
    def _device_info_dict(self) -> Dict:
        """Return the asset info."""
        return {**self._settlement_market_strategy.get_unsettled_deviation_dict(self)}

    @property
    def _progress_info(self) -> Dict:
        """Return the progress information of the simulation."""
        slot_completion_percent = int(
            (self.device.current_tick_in_slot / self.device.config.ticks_per_slot) * 100
        )
        return {
            "slot_completion": f"{slot_completion_percent}%",
            "market_slot": self.area.spot_market.time_slot_str,
        }

    def _dispatch_event_tick_to_external_agent(self) -> None:
        """
        Dispatch the tick event to devices either directly connected or connected
        through an aggregator.
        """
        if global_objects.external_global_stats.is_it_time_for_external_tick(
            self.device.current_tick
        ):
            if self.is_aggregator_controlled:
                self.redis.aggregator.add_batch_tick_event(self.device.uuid, self._progress_info)
            elif self.connected:
                current_tick_info = {
                    **self._progress_info,
                    "event": "tick",
                    "area_uuid": self.device.uuid,
                    "device_info": self._device_info_dict,
                }
                self.redis.publish_json(self.channel_names.tick, current_tick_info)

    def event_market_cycle(self) -> None:
        """Handler for the market cycle event."""
        if self.should_use_default_strategy:
            super().event_market_cycle()

    def publish_market_cycle(self):
        """Add the market cycle event to the device's aggregator events buffer."""
        if not self.should_use_default_strategy and self.is_aggregator_controlled:
            self.redis.aggregator.add_batch_market_event(self.device.uuid, self._progress_info)

    def _publish_trade_event(self, trade, is_bid_trade) -> None:
        """Publish trade event to external concerned device/aggregator."""
        if self.device.name not in (trade.seller.name, trade.buyer.name):
            # Trade does not concern this device, skip it.
            return

        if is_two_sided_market_simulation() and (
            (trade.buyer.uuid == self.device.uuid and not is_bid_trade)
            or (trade.seller.uuid == self.device.uuid and is_bid_trade)
        ):
            # Do not track a 2-sided market trade that is originating from an Offer to a
            # consumer (which should have posted a bid). This occurs when the clearing
            # took place on the area market of the device, thus causing 2 trades, one for
            # the bid clearing and one for the offer clearing.
            return

        if self.is_aggregator_controlled:
            event_response_dict = {
                "event": "trade",
                "asset_id": self.device.uuid,
                "trade_id": trade.id,
                "time": trade.creation_time.isoformat(),
                "trade_price": float(trade.trade_price),
                "traded_energy": float(trade.traded_energy),
                "total_fee": float(trade.fee_price),
                "local_market_fee": (
                    self.area.current_market.fee_class.grid_fee_rate
                    if self.area.current_market is not None
                    else "None"
                ),
                "seller": (
                    trade.seller.name if trade.seller.uuid == self.device.uuid else "anonymous"
                ),
                "buyer": trade.buyer.name if trade.buyer.uuid == self.device.uuid else "anonymous",
                "seller_origin": trade.seller.origin,
                "buyer_origin": trade.buyer.origin,
                "bid_id": trade.match_details["bid"].id if trade.is_bid_trade else "None",
                "offer_id": trade.match_details["offer"].id if trade.is_offer_trade else "None",
                "residual_bid_id": (
                    trade.residual.id
                    if trade.residual is not None and trade.is_bid_trade
                    else "None"
                ),
                "residual_offer_id": (
                    trade.residual.id
                    if trade.residual is not None and trade.is_offer_trade
                    else "None"
                ),
            }

            global_objects.external_global_stats.update()
            self.redis.aggregator.add_batch_trade_event(self.device.uuid, event_response_dict)
        elif self.connected:
            event_response_dict = {
                "device_info": self._device_info_dict,
                "event": "trade",
                "trade_id": trade.id,
                "time": trade.creation_time.isoformat(),
                "trade_price": float(trade.trade_price),
                "traded_energy": float(trade.traded_energy),
                "fee_price": float(trade.fee_price),
                "area_uuid": self.device.uuid,
                "seller": (
                    trade.seller.name if trade.seller.uuid == self.device.uuid else "anonymous"
                ),
                "buyer": trade.buyer.name if trade.buyer.uuid == self.device.uuid else "anonymous",
                "residual_id": trade.residual.id if trade.residual is not None else "None",
            }

            bid_offer_key = "bid_id" if is_bid_trade else "offer_id"
            event_response_dict["event_type"] = (
                "buy" if trade.buyer.name == self.device.name else "sell"
            )
            event_response_dict[bid_offer_key] = (
                trade.match_details["bid"].id if is_bid_trade else trade.match_details["offer"].id
            )

            self.redis.publish_json(self.channel_names.trade, event_response_dict)

    def event_bid_traded(self, market_id: str, bid_trade: Trade):
        """Handler for the event when a bid is accepted for trading."""
        super().event_bid_traded(market_id=market_id, bid_trade=bid_trade)
        if self.connected or self.is_aggregator_controlled:
            self._publish_trade_event(bid_trade, True)

    def event_offer_traded(self, market_id: str, trade: Trade):
        """Handler for the event when an offer is accepted for trading."""
        super().event_offer_traded(market_id=market_id, trade=trade)
        if self.connected or self.is_aggregator_controlled:
            self._publish_trade_event(trade, False)

    def deactivate(self):
        """Deactivate the area and notify the client."""
        super().deactivate()

        if self.is_aggregator_controlled:
            deactivate_msg = {"event": "finish"}
            self.redis.aggregator.add_batch_finished_event(self.owner.uuid, deactivate_msg)
        elif self.connected:
            deactivate_msg = {"event": "finish", "area_uuid": self.device.uuid}
            self.redis.publish_json(self.channel_names.finish, deactivate_msg)

    def _bid_aggregator(self, arguments: Dict):
        """Callback for the bid endpoint when sent by aggregator."""
        raise CommandTypeNotSupported(f"Bid command not supported on device {self.device.uuid}")

    def _delete_bid_aggregator(self, arguments: Dict):
        """Callback for the delete bid endpoint when sent by aggregator."""
        raise CommandTypeNotSupported(
            f"Delete bid command not supported on device {self.device.uuid}"
        )

    def _list_bids_aggregator(self, arguments: Dict):
        """Callback for the list bids endpoint when sent by aggregator."""
        raise CommandTypeNotSupported(
            f"List bids command not supported on device {self.device.uuid}"
        )

    def _offer_aggregator(self, arguments: Dict):
        """Callback for the offer endpoint when sent by aggregator."""
        raise CommandTypeNotSupported(f"Offer command not supported on device {self.device.uuid}")

    def _delete_offer_aggregator(self, arguments: Dict):
        """Callback for the delete offer endpoint when sent by aggregator."""
        raise CommandTypeNotSupported(
            f"Delete offer command not supported on device {self.device.uuid}"
        )

    def _list_offers_aggregator(self, arguments: Dict):
        """Callback for the list offers endpoint when sent by aggregator."""
        raise CommandTypeNotSupported(
            f"List offers command not supported on device {self.device.uuid}"
        )

    @property
    def _aggregator_command_callback_mapping(self) -> Dict:
        """Map the aggregator command types to their adjacent callbacks."""
        return {
            "bid": self._bid_aggregator,
            "delete_bid": self._delete_bid_aggregator,
            "list_bids": self._list_bids_aggregator,
            "offer": self._offer_aggregator,
            "delete_offer": self._delete_offer_aggregator,
            "list_offers": self._list_offers_aggregator,
            "device_info": self._device_info_aggregator,
        }

    def trigger_aggregator_commands(self, command: Dict) -> Dict:
        """Receive an aggregator command and call the corresponding callback.

        Raises:
            CommandTypeNotSupported: The client sent a unsupported command
        """
        try:
            command_type = command.get("type")
            if command_type is None:
                return {
                    "status": "error",
                    "area_uuid": self.device.uuid,
                    "message": "Invalid command type",
                }

            callback = self._aggregator_command_callback_mapping.get(command["type"])
            if callback is None:
                return {
                    "command": command["type"],
                    "status": "error",
                    "area_uuid": self.device.uuid,
                    "message": f"Command type not supported for device {self.device.uuid}",
                }
            response = callback(command)
        except CommandTypeNotSupported as e:
            response = {
                "command": command["type"],
                "status": "error",
                "area_uuid": self.device.uuid,
                "message": str(e),
            }
        return response

    def _reject_all_pending_requests(self) -> None:
        """Reject all pending requests queue and notify the client."""
        for req in self.pending_requests:
            self.redis.publish_json(
                req.response_channel,
                {
                    "command": f"{req.request_type}",
                    "status": "error",
                    "error_message": f"Error when handling {req.request_type} "
                    f"on area {self.device.name} with arguments {req.arguments}."
                    "Market cycle already finished.",
                },
            )
        self.pending_requests = deque()

    @property
    def market_info_dict(self) -> Dict:
        """Return the latest statistics info of the asset."""
        return {
            "asset_info": self._device_info_dict,
            "last_slot_asset_info": {
                "energy_traded": (
                    self.energy_traded(self.area.current_market.id)
                    if self.area.current_market
                    else None
                ),
                "total_cost": (
                    self.energy_traded_costs(self.area.current_market.id)
                    if self.area.current_market
                    else None
                ),
            },
            "asset_bill": self.device.stats.aggregated_stats.get("bills"),
        }

    def populate_market_info_to_connected_user(self) -> None:
        """Publish market info to the user who is connected directly from SDK."""
        market_info = self.spot_market.info
        market_info["device_info"] = self._device_info_dict
        market_info["event"] = "market"
        market_info["area_uuid"] = self.device.uuid
        market_info["device_bill"] = self.device.stats.aggregated_stats.get("bills")
        market_info["last_market_maker_rate"] = get_market_maker_rate_from_config(
            self.area.current_market
        )
        market_info["last_market_stats"] = self.area.stats.get_price_stats_current_market()
        self.redis.publish_json(self.channel_names.market, market_info)

    def filter_degrees_of_freedom_arguments(self, order_arguments: Dict) -> Tuple[Dict, List[str]]:
        """Filter the arguments of an incoming order to remove Degrees of Freedom if necessary."""
        if self.simulation_config.enable_degrees_of_freedom:
            return order_arguments, []

        order_arguments, filtered_fields = DegreesOfFreedomFilter.apply(order_arguments)

        return order_arguments, filtered_fields
