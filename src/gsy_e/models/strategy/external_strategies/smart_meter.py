# pylint: disable=broad-except,fixme
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

from gsy_e.models.market import MarketBase
from gsy_e.models.strategy.external_strategies import (ExternalMixin,
                                                       ExternalStrategyConnectionManager,
                                                       IncomingRequest)
from gsy_e.models.strategy.smart_meter import SmartMeterStrategy

if TYPE_CHECKING:
    from gsy_e.models.strategy import Offers
    from gsy_e.models.strategy.smart_meter import SmartMeterState


class SmartMeterExternalMixin(ExternalMixin):
    """
    Mixin for enabling an external api for the SmartMeter strategies.
    Should always be inherited together with a superclass of SmartMeterStrategy.
    """

    state: "SmartMeterState"
    offers: "Offers"
    is_bid_posted: Callable
    _delete_past_state: Callable
    post_bid: Callable
    post_offer: Callable
    can_bid_be_posted: Callable
    can_offer_be_posted: Callable
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
            f"{self.channel_prefix}/offer": self.offer,
            f"{self.channel_prefix}/delete_offer": self.delete_offer,
            f"{self.channel_prefix}/list_offers": self.list_offers,
            f"{self.channel_prefix}/bid": self.bid,
            f"{self.channel_prefix}/delete_bid": self.delete_bid,
            f"{self.channel_prefix}/list_bids": self.list_bids,
        })

    def event_market_cycle(self) -> None:
        """Handler for the market cycle event."""
        self._reject_all_pending_requests()
        self._update_connection_status()
        if not self.should_use_default_strategy:
            # TODO: Update states?
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
                                            "time_slot",
                                            "attributes",
                                            "requirements"})
        offer_response_channel = f"{self.channel_prefix}/response/offer"
        if not ExternalStrategyConnectionManager.check_for_connected_and_reply(
                self.redis, offer_response_channel, self.connected):
            return
        try:
            arguments = json.loads(payload["data"])
            # Check that all required arguments have been provided
            assert all(arg in arguments.keys() for arg in required_args)
            # Check that every provided argument is allowed
            assert all(arg in allowed_args for arg in arguments.keys())
        except Exception: # noqa
            logging.exception("Incorrect offer request. Payload %s.", payload)
            self.redis.publish_json(
                offer_response_channel,
                {"command": "offer",
                 "error": (
                     "Incorrect offer request. "
                     "Available parameters: ('price', 'energy', 'replace_existing')."),
                 "transaction_id": transaction_id})
        else:
            self.pending_requests.append(
                IncomingRequest("offer", arguments, offer_response_channel))

    def delete_offer(self, payload: Dict) -> None:
        """Callback for delete offer Redis endpoint."""
        transaction_id = self._get_transaction_id(payload)
        delete_offer_response_channel = f"{self.channel_prefix}/response/delete_offer"
        if not ExternalStrategyConnectionManager.check_for_connected_and_reply(
                self.redis, delete_offer_response_channel, self.connected):
            return
        try:
            arguments = json.loads(payload["data"])
            market = self._get_market_from_command_argument(arguments)
            if arguments.get("offer") and not self.offers.is_offer_posted(
                    market.id, arguments["offer"]):
                raise Exception("Offer_id is not associated with any posted offer.")
        except Exception: # noqa
            logging.exception("Error when handling delete offer request. Payload %s", payload)
            self.redis.publish_json(
                delete_offer_response_channel,
                {"command": "offer_delete",
                 "error": "Incorrect delete offer request. Available parameters: (offer).",
                 "transaction_id": transaction_id})
        else:
            self.pending_requests.append(
                IncomingRequest("delete_offer", arguments, delete_offer_response_channel))

    def list_offers(self, payload: Dict) -> None:
        """Callback for list offers Redis endpoint."""
        assert self._get_transaction_id(payload)
        list_offers_response_channel = f"{self.channel_prefix}/response/list_offers"
        if not ExternalStrategyConnectionManager.check_for_connected_and_reply(
                self.redis, list_offers_response_channel, self.connected):
            return
        arguments = json.loads(payload["data"])
        self.pending_requests.append(
            IncomingRequest("list_offers", arguments, list_offers_response_channel))

    def bid(self, payload: Dict) -> None:
        """Callback for bid Redis endpoint."""
        transaction_id = self._get_transaction_id(payload)
        required_args = {"price", "energy", "transaction_id"}
        allowed_args = required_args.union({"replace_existing",
                                            "time_slot",
                                            "attributes",
                                            "requirements"})
        bid_response_channel = f"{self.channel_prefix}/response/bid"
        if not ExternalStrategyConnectionManager.check_for_connected_and_reply(
                self.redis, bid_response_channel, self.connected):
            return
        try:
            arguments = json.loads(payload["data"])

            # Check that all required arguments have been provided
            assert all(arg in arguments.keys() for arg in required_args)
            # Check that every provided argument is allowed
            assert all(arg in allowed_args for arg in arguments.keys())
        except Exception: # noqa
            self.redis.publish_json(
                bid_response_channel,
                {"command": "bid",
                 "error": (
                     "Incorrect bid request. "
                     "Available parameters: ('price', 'energy', 'replace_existing')."),
                 "transaction_id": transaction_id})
        else:
            self.pending_requests.append(
                IncomingRequest("bid", arguments, bid_response_channel))

    def delete_bid(self, payload: Dict) -> None:
        """Callback for delete bid Redis endpoint."""
        transaction_id = self._get_transaction_id(payload)
        delete_bid_response_channel = f"{self.channel_prefix}/response/delete_bid"
        if not ExternalStrategyConnectionManager.check_for_connected_and_reply(
                self.redis, delete_bid_response_channel, self.connected):
            return
        try:
            arguments = json.loads(payload["data"])
            market = self._get_market_from_command_argument(arguments)
            if arguments.get("bid") and not self.is_bid_posted(market, arguments["bid"]):
                raise Exception("Bid_id is not associated with any posted bid.")
        except Exception as e:
            self.redis.publish_json(
                delete_bid_response_channel,
                {"command": "bid_delete",
                 "error": "Incorrect delete bid request. Available parameters: (bid)."
                          f"Exception: {str(e)}",
                 "transaction_id": transaction_id}
            )
        else:
            self.pending_requests.append(
                IncomingRequest("delete_bid", arguments, delete_bid_response_channel))

    def list_bids(self, payload: Dict) -> None:
        """Callback for list bids Redis endpoint."""
        assert self._get_transaction_id(payload)
        list_bids_response_channel = f"{self.channel_prefix}/response/list_bids"
        if not ExternalStrategyConnectionManager.check_for_connected_and_reply(
                self.redis, list_bids_response_channel, self.connected):
            return
        arguments = json.loads(payload["data"])
        self.pending_requests.append(
            IncomingRequest("list_bids", arguments, list_bids_response_channel))

    def _incoming_commands_callback_selection(self, req: IncomingRequest) -> None:
        """
        Actually handle incoming requests that are validated by the corresponding function.
        e.g. New bids are first checked by the `bid` function and put into the `pending_requests`
        queue. Then, requests are handled on each tick using this dispatcher function.
        """
        if req.request_type == "bid":
            self._bid_impl(req.arguments, req.response_channel)
        elif req.request_type == "delete_bid":
            self._delete_bid_impl(req.arguments, req.response_channel)
        elif req.request_type == "list_bids":
            self._list_bids_impl(req.arguments, req.response_channel)
        elif req.request_type == "offer":
            self._offer_impl(req.arguments, req.response_channel)
        elif req.request_type == "delete_offer":
            self._delete_offer_impl(req.arguments, req.response_channel)
        elif req.request_type == "list_offers":
            self._list_offers_impl(req.arguments, req.response_channel)
        elif req.request_type == "device_info":
            self._device_info_impl(req.arguments, req.response_channel)
        else:
            assert False, f"Incorrect incoming request name: {req}"

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
            if v.seller == self.device.name]

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
            if bid.buyer == self.device.name]

    def _bid_impl(self, arguments: Dict, response_channel: str) -> None:
        """Post the bid to the market."""
        market = self._get_market_from_command_argument(arguments)
        try:
            response_message = ""
            arguments, filtered_fields = self.filter_degrees_of_freedom_arguments(arguments)
            if filtered_fields:
                response_message = (
                    "The following arguments are not supported for this market and have been "
                    f"removed from your order: {filtered_fields}.")
            replace_existing = arguments.get("replace_existing", True)
            assert self.can_bid_be_posted(market.time_slot, **arguments)
            bid = self.post_bid(
                market,
                arguments["price"],
                arguments["energy"],
                replace_existing=replace_existing,
                attributes=arguments.get("attributes"),
                requirements=arguments.get("requirements")
            )
            response = {
                "command": "bid",
                "status": "ready",
                "bid": bid.to_json_string(replace_existing=replace_existing),
                "market_type": market.type_name,
                "transaction_id": arguments.get("transaction_id"),
                "message": response_message}
        except Exception: # noqa
            logging.exception("Error when handling bid create on area %s: Bid Arguments: %s",
                              self.device.name, arguments)
            response = {"command": "bid", "status": "error",
                        "market_type": market.type_name,
                        "error_message": "Error when handling bid create "
                                         f"on area {self.device.name} with arguments {arguments}.",
                        "transaction_id": arguments.get("transaction_id")}

        self.redis.publish_json(response_channel, response)

    def _delete_bid_impl(self, arguments: Dict, response_channel: str) -> None:
        """Delete a bid from the market."""
        try:
            market = self._get_market_from_command_argument(arguments)
            to_delete_bid_id = arguments.get("bid")
            deleted_bids = self.remove_bid_from_pending(market.id, bid_id=to_delete_bid_id)
            self.redis.publish_json(
                response_channel,
                {"command": "bid_delete", "status": "ready", "deleted_bids": deleted_bids,
                 "transaction_id": arguments.get("transaction_id")})
        except Exception: # noqa
            logging.exception("Error when handling bid delete on area %s: Bid Arguments: %s",
                              self.device.name, arguments)
            self.redis.publish_json(
                response_channel,
                {"command": "bid_delete", "status": "error",
                 "error_message": "Error when handling bid delete "
                                  f"on area {self.device.name} with arguments {arguments}.",
                 "transaction_id": arguments.get("transaction_id")})

    def _list_bids_impl(self, arguments: Dict, response_channel: str) -> None:
        """List sent bids to the market."""
        try:
            market = self._get_market_from_command_argument(arguments)
            response = {
                "command": "list_bids", "status": "ready",
                "bid_list": self.filtered_market_bids(market),
                "transaction_id": arguments.get("transaction_id")}
        except Exception: # noqa
            error_message = f"Error when handling list bids on area {self.device.name}"
            logging.exception(error_message)
            response = {"command": "list_bids", "status": "error",
                        "error_message": error_message,
                        "transaction_id": arguments.get("transaction_id")}
        self.redis.publish_json(response_channel, response)

    def _offer_impl(self, arguments: Dict, response_channel: str) -> None:
        """Post the offer to the market."""
        market = self._get_market_from_command_argument(arguments)
        try:
            replace_existing = arguments.pop("replace_existing", True)
            assert self.can_offer_be_posted(
                arguments["energy"],
                arguments["price"],
                self.state.get_available_energy_kWh(market.time_slot),
                market,
                replace_existing=replace_existing)

            offer_arguments = {
                k: v for k, v in arguments.items() if k not in ["transaction_id", "time_slot"]}
            offer = self.post_offer(
                market, replace_existing=replace_existing, **offer_arguments)

            self.redis.publish_json(
                response_channel,
                {"command": "offer", "status": "ready",
                 "market_type": market.type_name,
                 "offer": offer.to_json_string(replace_existing=replace_existing),
                 "transaction_id": arguments.get("transaction_id")})
        except Exception: # noqa
            error_message = (f"Error when handling offer create on area {self.device.name}: "
                             f"Offer Arguments: {arguments}")
            logging.exception(error_message)
            self.redis.publish_json(
                response_channel,
                {"command": "offer", "status": "error",
                 "market_type": market.type_name,
                 "error_message": error_message,
                 "transaction_id": arguments.get("transaction_id")})

    def _delete_offer_impl(self, arguments: Dict, response_channel: str) -> None:
        """Delete an offer from the market."""
        try:
            market = self._get_market_from_command_argument(arguments)
            to_delete_offer_id = arguments.get("offer")
            deleted_offers = self.offers.remove_offer_from_cache_and_market(
                market, to_delete_offer_id)
            response = {"command": "offer_delete", "status": "ready",
                        "deleted_offers": deleted_offers,
                        "transaction_id": arguments.get("transaction_id")}
        except Exception: # noqa
            error_message = (f"Error when handling offer delete on area {self.device.name}: "
                             f"Offer Arguments: {arguments}")
            logging.exception(error_message)
            response = {"command": "offer_delete", "status": "error",
                        "error_message": error_message,
                        "transaction_id": arguments.get("transaction_id")}
        self.redis.publish_json(response_channel, response)

    def _list_offers_impl(self, arguments: Dict, response_channel: str) -> None:
        """List sent offers to the market."""
        try:
            market = self._get_market_from_command_argument(arguments)
            response = {"command": "list_offers", "status": "ready",
                        "offer_list": self.filtered_market_offers(market),
                        "transaction_id": arguments.get("transaction_id")}
        except Exception: # noqa
            error_message = f"Error when handling list offers on area {self.device.name}"
            logging.exception(error_message)
            response = {"command": "list_offers", "status": "error",
                        "error_message": error_message,
                        "transaction_id": arguments.get("transaction_id")}
        self.redis.publish_json(response_channel, response)


class SmartMeterExternalStrategy(SmartMeterExternalMixin, SmartMeterStrategy):
    """Strategy class for external SmartMeter devices."""
