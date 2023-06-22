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
from typing import TYPE_CHECKING, Callable, Dict, List
from gsy_framework.utils import str_to_pendulum_datetime
from gsy_e.models.market import MarketBase
from gsy_e.models.strategy.external_strategies import (ExternalMixin,
                                                       ExternalStrategyConnectionManager,
                                                       IncomingRequest, OrderCanNotBePosted)
from gsy_e.models.strategy.smart_meter import SmartMeterStrategy

if TYPE_CHECKING:
    from pendulum import DateTime

    from gsy_e.models.strategy import Offers
    from gsy_e.models.strategy.energy_parameters.smart_meter import (
        SmartMeterEnergyParameters, SmartMeterState)

logger = logging.getLogger(__name__)


class SmartMeterExternalMixin(ExternalMixin):
    """
    Mixin for enabling an external api for the SmartMeter strategies.
    Should always be inherited together with a superclass of SmartMeterStrategy.
    """
    # pylint: disable=broad-except
    # state
    state: "SmartMeterState"
    _delete_past_state: Callable
    _energy_params: "SmartMeterEnergyParameters"
    _set_energy_measurement_of_last_market: Callable
    spot_market_time_slot: "DateTime"
    # offer
    offers: "Offers"
    post_offer: Callable
    can_offer_be_posted: Callable
    # bid
    post_bid: Callable
    can_bid_be_posted: Callable
    is_bid_posted: Callable
    remove_bid_from_pending: Callable

    @property
    def _device_info_dict(self) -> Dict:
        """Return the asset info."""
        return {
            **super()._device_info_dict,
            **self.state.to_dict(self.spot_market.time_slot)
        }

    def event_activate(self, **kwargs) -> None:
        """Activate the device."""
        super().event_activate(**kwargs) # noqa
        self.redis.sub_to_multiple_channels({
            **super().channel_dict,
            self.channel_names.offer: self.offer,
            self.channel_names.delete_offer: self.delete_offer,
            self.channel_names.list_offers: self.list_offers,
            self.channel_names.bid: self.bid,
            self.channel_names.delete_bid: self.delete_bid,
            self.channel_names.list_bids: self.list_bids,
        })

    def event_market_cycle(self) -> None:
        """Handler for the market cycle event."""
        self._reject_all_pending_requests()
        self._update_connection_status()
        if not self.should_use_default_strategy:
            self._energy_params.set_energy_forecast_for_future_markets(
                [self.spot_market_time_slot, *self.area.future_market_time_slots],
                reconfigure=False)
            self._set_energy_measurement_of_last_market()
            if not self.is_aggregator_controlled:
                self.populate_market_info_to_connected_user()
            self._delete_past_state()
        else:
            super().event_market_cycle()

    def event_tick(self) -> None:
        """Process aggregator requests on market tick. Extends super implementation."""
        if not self.connected and not self.is_aggregator_controlled:
            super().event_tick() # noqa
        else:
            while self.pending_requests:
                # We want to process requests as First-In-First-Out, so we use popleft
                req = self.pending_requests.popleft()
                self._incoming_commands_callback_selection(req)
            self._dispatch_event_tick_to_external_agent()

    def offer(self, payload: Dict) -> None:
        """Callback for offer Redis endpoint."""
        transaction_id = self._get_transaction_id(payload)
        required_args = {"price", "energy", "transaction_id"}
        allowed_args = required_args.union({"replace_existing",
                                            "time_slot"})
        response_channel = self.channel_names.offer_response
        if not ExternalStrategyConnectionManager.check_for_connected_and_reply(
                self.redis, response_channel, self.connected):
            return
        try:
            arguments = json.loads(payload["data"])
            # Check that all required arguments have been provided
            assert all(arg in arguments.keys() for arg in required_args)
            # Check that every provided argument is allowed
            assert all(arg in allowed_args for arg in arguments.keys())
        except Exception: # noqa
            logger.exception("Incorrect offer request. Payload %s.", payload)
            self.redis.publish_json(
                response_channel,
                {"command": "offer",
                 "error": (
                     "Incorrect offer request. "
                     "Available parameters: ('price', 'energy', 'replace_existing')."),
                 "transaction_id": transaction_id})
        else:
            self.pending_requests.append(
                IncomingRequest("offer", arguments, response_channel))

    def delete_offer(self, payload: Dict) -> None:
        """Callback for delete offer Redis endpoint."""
        transaction_id = self._get_transaction_id(payload)
        response_channel = self.channel_names.delete_offer_response
        if not ExternalStrategyConnectionManager.check_for_connected_and_reply(
                self.redis, response_channel, self.connected):
            return
        try:
            arguments = json.loads(payload["data"])
            market = self._get_market_from_command_argument(arguments)
            if arguments.get("offer") and not self.offers.is_offer_posted(
                    market.id, arguments["offer"]):
                raise Exception("Offer_id is not associated with any posted offer.")
        except Exception: # noqa
            logger.exception("Error when handling delete offer request. Payload %s", payload)
            self.redis.publish_json(
                response_channel,
                {"command": "offer_delete",
                 "error": "Incorrect delete offer request. Available parameters: (offer).",
                 "transaction_id": transaction_id})
        else:
            self.pending_requests.append(
                IncomingRequest("delete_offer", arguments, response_channel))

    def list_offers(self, payload: Dict) -> None:
        """Callback for list offers Redis endpoint."""
        assert self._get_transaction_id(payload)
        response_channel = self.channel_names.list_offers_response
        if not ExternalStrategyConnectionManager.check_for_connected_and_reply(
                self.redis, response_channel, self.connected):
            return
        arguments = json.loads(payload["data"])
        self.pending_requests.append(
            IncomingRequest("list_offers", arguments, response_channel))

    def bid(self, payload: Dict) -> None:
        """Callback for bid Redis endpoint."""
        transaction_id = self._get_transaction_id(payload)
        required_args = {"price", "energy", "transaction_id"}
        allowed_args = required_args.union({"replace_existing",
                                            "time_slot"})
        response_channel = self.channel_names.bid_response
        if not ExternalStrategyConnectionManager.check_for_connected_and_reply(
                self.redis, response_channel, self.connected):
            return
        try:
            arguments = json.loads(payload["data"])

            # Check that all required arguments have been provided
            assert all(arg in arguments.keys() for arg in required_args)
            # Check that every provided argument is allowed
            assert all(arg in allowed_args for arg in arguments.keys())
        except Exception: # noqa
            self.redis.publish_json(
                response_channel,
                {"command": "bid",
                 "error": (
                     "Incorrect bid request. "
                     "Available parameters: ('price', 'energy', 'replace_existing')."),
                 "transaction_id": transaction_id})
        else:
            self.pending_requests.append(
                IncomingRequest("bid", arguments, response_channel))

    def delete_bid(self, payload: Dict) -> None:
        """Callback for delete bid Redis endpoint."""
        transaction_id = self._get_transaction_id(payload)
        response_channel = self.channel_names.delete_bid_response
        if not ExternalStrategyConnectionManager.check_for_connected_and_reply(
                self.redis, response_channel, self.connected):
            return
        try:
            arguments = json.loads(payload["data"])
            market = self._get_market_from_command_argument(arguments)
            if arguments.get("bid") and not self.is_bid_posted(market, arguments["bid"]):
                raise Exception("Bid_id is not associated with any posted bid.")
        except Exception as e:
            self.redis.publish_json(
                response_channel,
                {"command": "bid_delete",
                 "error": "Incorrect delete bid request. Available parameters: (bid)."
                          f"Exception: {str(e)}",
                 "transaction_id": transaction_id}
            )
        else:
            self.pending_requests.append(
                IncomingRequest("delete_bid", arguments, response_channel))

    def list_bids(self, payload: Dict) -> None:
        """Callback for list bids Redis endpoint."""
        assert self._get_transaction_id(payload)
        response_channel = self.channel_names.list_bids_response
        if not ExternalStrategyConnectionManager.check_for_connected_and_reply(
                self.redis, response_channel, self.connected):
            return
        arguments = json.loads(payload["data"])
        self.pending_requests.append(
            IncomingRequest("list_bids", arguments, response_channel))

    def _incoming_commands_callback_selection(self, req: IncomingRequest) -> None:
        """
        Actually handle incoming requests that are validated by the corresponding function.
        e.g. New bids are first checked by the `bid` function and put into the `pending_requests`
        queue. Then, requests are handled on each tick using this dispatcher function.
        """
        response = self.trigger_aggregator_commands(req.arguments)
        self.redis.publish_json(req.response_channel, response)

    def filtered_market_offers(self, market: MarketBase) -> List[Dict]:
        """
        Get a representation of each of the asset's offers from the market.
        Args:
            market: Market object that will read the offers from

        Returns: List of offers for the strategy asset
        """
        return [
            {"id": v.id, "price": v.price, "energy": v.energy}
            for _, v in market.get_offers().items()
            if v.seller.name == self.device.name]

    def filtered_market_bids(self, market: MarketBase) -> List[Dict]:
        """
        Get a representation of each of the asset's bids from the market.
        Args:
            market: Market object that will read the bids from

        Returns: List of bids for the strategy asset
        """
        return [
            {"id": bid.id, "price": bid.price, "energy": bid.energy}
            for _, bid in market.get_bids().items()
            if bid.buyer.name == self.device.name]

    def _bid_aggregator(self, arguments: Dict) -> Dict:
        """Post the bid to the market."""
        try:
            market = self._get_market_from_command_argument(arguments)
            response_message = ""
            arguments, filtered_fields = self.filter_degrees_of_freedom_arguments(arguments)
            if filtered_fields:
                response_message = (
                    "The following arguments are not supported for this market and have been "
                    f"removed from your order: {filtered_fields}.")
            time_slot = (str_to_pendulum_datetime(arguments["time_slot"])
                         if arguments.get("time_slot") else None)
            if self.area.is_market_settlement(market.id):
                if not self.state.can_post_settlement_bid(market.time_slot):
                    raise OrderCanNotBePosted("The smart meter did not consume enough energy, "
                                              "settlement bid can not be posted.")
                required_energy = self.state.get_unsettled_deviation_kWh(market.time_slot)
            elif self.area.is_market_future(market.id):
                required_energy = self.state.get_energy_requirement_Wh(time_slot) / 1000
            elif self.area.is_market_spot(market.id):
                required_energy = (
                    self.state.get_energy_requirement_Wh(market.time_slot) / 1000)
            else:
                logger.debug("The order cannot be posted on the market. "
                             "(arguments: %s, market_id: %s", arguments, market.id)
                raise OrderCanNotBePosted("The order cannot be posted on the market.")
            replace_existing = arguments.get("replace_existing", True)
            assert self.can_bid_be_posted(
                arguments["energy"],
                arguments["price"],
                required_energy,
                market,
                replace_existing
            )
            bid = self.post_bid(
                market,
                arguments["price"],
                arguments["energy"],
                replace_existing=replace_existing,
                time_slot=time_slot
            )
            response = {
                "command": "bid",
                "status": "ready",
                "area_uuid": self.device.uuid,
                "bid": bid.to_json_string(),
                "market_type": market.type_name,
                "transaction_id": arguments.get("transaction_id"),
                "message": response_message}
        except Exception: # noqa
            logger.exception("Error when handling bid create on area %s: Bid Arguments: %s",
                             self.device.name, arguments)
            response = {"command": "bid", "status": "error",
                        "market_type": market.type_name,
                        "area_uuid": self.device.uuid,
                        "error_message": "Error when handling bid create "
                                         f"on area {self.device.name} with arguments {arguments}.",
                        "transaction_id": arguments.get("transaction_id")}
        return response

    def _delete_bid_aggregator(self, arguments: Dict) -> Dict:
        """Delete a bid from the market."""
        try:
            market = self._get_market_from_command_argument(arguments)
            to_delete_bid_id = arguments.get("bid")
            deleted_bids = self.remove_bid_from_pending(market.id, bid_id=to_delete_bid_id)
            response = {"command": "bid_delete", "status": "ready", "deleted_bids": deleted_bids,
                        "area_uuid": self.device.uuid,
                        "transaction_id": arguments.get("transaction_id")}
        except Exception: # noqa
            logger.exception("Error when handling bid delete on area %s: Bid Arguments: %s",
                             self.device.name, arguments)
            response = {"command": "bid_delete", "status": "error",
                        "error_message": "Error when handling bid delete "
                                         f"on area {self.device.name} with arguments {arguments}.",
                        "area_uuid": self.device.uuid,
                        "transaction_id": arguments.get("transaction_id")}
        return response

    def _list_bids_aggregator(self, arguments: Dict) -> Dict:
        """List sent bids to the market."""
        try:
            market = self._get_market_from_command_argument(arguments)
            response = {
                "command": "list_bids", "status": "ready",
                "bid_list": self.filtered_market_bids(market),
                "area_uuid": self.device.uuid,
                "transaction_id": arguments.get("transaction_id")}
        except Exception: # noqa
            error_message = f"Error when handling list bids on area {self.device.name}"
            logger.exception(error_message)
            response = {"command": "list_bids", "status": "error",
                        "error_message": error_message,
                        "area_uuid": self.device.uuid,
                        "transaction_id": arguments.get("transaction_id")}
        return response

    def _offer_aggregator(self, arguments: Dict) -> Dict:
        """Post the offer to the market."""
        try:
            market = self._get_market_from_command_argument(arguments)
            response_message = ""
            arguments, filtered_fields = self.filter_degrees_of_freedom_arguments(arguments)
            if filtered_fields:
                response_message = (
                    "The following arguments are not supported for this market and have been "
                    f"removed from your order: {filtered_fields}.")
            if self.area.is_market_settlement(market.id):
                if not self.state.can_post_settlement_offer(market.time_slot):
                    raise OrderCanNotBePosted("The smart meter did not produce enough energy, ",
                                              "settlement offer can not be posted.")
                available_energy = self.state.get_unsettled_deviation_kWh(market.time_slot)
            elif self.area.is_market_future(market.id):
                available_energy = self.state.get_available_energy_kWh(
                    str_to_pendulum_datetime(arguments["time_slot"]))
            elif self.area.is_market_spot(market.id):
                available_energy = self.state.get_available_energy_kWh(market.time_slot)
            else:
                logger.debug("The order cannot be posted on the market. "
                             "(arguments: %s, market_id: %s", arguments, market.id)
                raise OrderCanNotBePosted("The order cannot be posted on the market.")

            replace_existing = arguments.pop("replace_existing", True)
            assert self.can_offer_be_posted(
                arguments["energy"],
                arguments["price"],
                available_energy,
                market,
                replace_existing)
            offer_arguments = {
                k: v for k, v in arguments.items()
                if k not in ["transaction_id", "type"]}
            offer = self.post_offer(
                market,
                replace_existing,
                **offer_arguments)
            response = {"command": "offer", "status": "ready",
                        "market_type": market.type_name,
                        "offer": offer.to_json_string(),
                        "area_uuid": self.device.uuid,
                        "transaction_id": arguments.get("transaction_id"),
                        "message": response_message}
        except Exception: # noqa
            error_message = (f"Error when handling offer create on area {self.device.name}: "
                             f"Offer Arguments: {arguments}")
            logger.exception(error_message)
            response = {"command": "offer", "status": "error",
                        "market_type": market.type_name,
                        "error_message": error_message,
                        "area_uuid": self.device.uuid,
                        "transaction_id": arguments.get("transaction_id")}
        return response

    def _delete_offer_aggregator(self, arguments: Dict) -> Dict:
        """Delete an offer from the market."""
        try:
            market = self._get_market_from_command_argument(arguments)
            to_delete_offer_id = arguments.get("offer")
            deleted_offers = self.offers.remove_offer_from_cache_and_market(
                market, to_delete_offer_id)
            response = {"command": "offer_delete", "status": "ready",
                        "deleted_offers": deleted_offers,
                        "area_uuid": self.device.uuid,
                        "transaction_id": arguments.get("transaction_id")}
        except Exception: # noqa
            error_message = (f"Error when handling offer delete on area {self.device.name}: "
                             f"Offer Arguments: {arguments}")
            logger.exception(error_message)
            response = {"command": "offer_delete", "status": "error",
                        "error_message": error_message,
                        "area_uuid": self.device.uuid,
                        "transaction_id": arguments.get("transaction_id")}
        return response

    def _list_offers_aggregator(self, arguments: Dict) -> Dict:
        """List sent offers to the market."""
        try:
            market = self._get_market_from_command_argument(arguments)
            response = {"command": "list_offers", "status": "ready",
                        "offer_list": self.filtered_market_offers(market),
                        "area_uuid": self.device.uuid,
                        "transaction_id": arguments.get("transaction_id")}
        except Exception: # noqa
            error_message = f"Error when handling list offers on area {self.device.name}"
            logger.exception(error_message)
            response = {"command": "list_offers", "status": "error",
                        "error_message": error_message,
                        "area_uuid": self.device.uuid,
                        "transaction_id": arguments.get("transaction_id")}
        return response


class SmartMeterExternalStrategy(SmartMeterExternalMixin, SmartMeterStrategy):
    """Strategy class for external SmartMeter devices."""
