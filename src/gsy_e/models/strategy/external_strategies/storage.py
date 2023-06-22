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

from gsy_framework.utils import str_to_pendulum_datetime
from pendulum import DateTime

from gsy_e.models.market import MarketBase
from gsy_e.models.strategy.external_strategies import (ExternalMixin,
                                                       ExternalStrategyConnectionManager,
                                                       IncomingRequest)
from gsy_e.models.strategy.storage import StorageStrategy

if TYPE_CHECKING:
    from gsy_e.models.strategy.state import StorageState
    from gsy_e.models.strategy import Offers


class StorageExternalMixin(ExternalMixin):
    """
    Mixin for enabling an external api for the storage strategies.
    Should always be inherited together with a superclass of StorageStrategy.
    """

    state: "StorageState"
    offers: "Offers"
    post_offer: Callable
    is_bid_posted: Callable
    remove_bid_from_pending: Callable
    posted_bid_energy: Callable
    post_bid: Callable
    _delete_past_state: Callable
    _cycle_state: Callable

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

    def event_activate(self, **kwargs) -> None:
        """Activate the device."""
        super().event_activate(**kwargs)
        self.redis.sub_to_multiple_channels({
            **super().channel_dict,
            self.channel_names.offer: self.offer,
            self.channel_names.delete_offer: self.delete_offer,
            self.channel_names.list_offers: self.list_offers,
            self.channel_names.bid: self.bid,
            self.channel_names.delete_bid: self.delete_bid,
            self.channel_names.list_bids: self.list_bids,
        })

    def list_offers(self, payload: Dict) -> None:
        """Callback for list offers Redis endpoint."""
        self._get_transaction_id(payload)
        response_channel = self.channel_names.list_offers_response
        if not ExternalStrategyConnectionManager.check_for_connected_and_reply(
                self.redis, response_channel, self.connected):
            return
        arguments = json.loads(payload["data"])
        self.pending_requests.append(
            IncomingRequest("list_offers", arguments, response_channel))

    def _list_offers_impl(self, arguments: Dict, response_channel: str) -> None:
        """Implementation for the list_offers callback, publish this device offers."""
        try:
            market = self._get_market_from_command_argument(arguments)
            filtered_offers = [{"id": v.id, "price": v.price, "energy": v.energy}
                               for _, v in market.get_offers().items()
                               if v.seller.name == self.device.name]
            response = {"command": "list_offers", "status": "ready",
                        "offer_list": filtered_offers,
                        "transaction_id": arguments.get("transaction_id")}
        except Exception:
            logging.exception("Error when handling list offers on area %s", self.device.name)
            response = {"command": "list_offers", "status": "error",
                        "error_message": f"Error when listing offers on area {self.device.name}.",
                        "transaction_id": arguments.get("transaction_id")}
        self.redis.publish_json(response_channel, response)

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
        except Exception:
            logging.exception("Error when handling delete offer request. Payload %s", payload)
            self.redis.publish_json(
                response_channel,
                {"command": "offer_delete",
                 "error": "Incorrect delete offer request. Available parameters: (offer).",
                 "transaction_id": transaction_id})
        else:
            self.pending_requests.append(
                IncomingRequest("delete_offer", arguments, response_channel))

    def _delete_offer_impl(self, arguments: Dict, response_channel: str) -> None:
        """Implementation for the delete_offer callback, delete the received offer from market."""
        try:
            market = self._get_market_from_command_argument(arguments)
            to_delete_offer_id = arguments.get("offer")
            deleted_offers = self.offers.remove_offer_from_cache_and_market(
                market, to_delete_offer_id)
            self.state.reset_offered_sell_energy(
                self.offers.open_offer_energy(market.id), market.time_slot)
            response = {"command": "offer_delete", "status": "ready",
                        "deleted_offers": deleted_offers,
                        "transaction_id": arguments.get("transaction_id")}
        except Exception:
            logging.exception("Error when handling offer delete on area %s: Offer Arguments: %s",
                              self.device.name, arguments)
            response = {"command": "offer_delete", "status": "error",
                        "error_message": "Error when handling offer delete "
                                         f"on area {self.device.name} with arguments {arguments}.",
                        "transaction_id": arguments.get("transaction_id")}
        self.redis.publish_json(response_channel, response)

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

        except Exception:
            logging.exception("Incorrect offer request. Payload %s.", payload)
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

    def can_offer_be_posted(self, time_slot: DateTime, offer_arguments: Dict):
        """Check that the energy being offered is <= than the energy available to be sold."""
        # TODO: Should be removed within D3ASIM-3671
        replace_existing = offer_arguments.get("replace_existing", True)
        if replace_existing:
            # Do not consider previously offered energy, since those offers would be deleted
            return (
                offer_arguments["energy"] <=
                self.state.energy_to_sell_dict[time_slot] +
                self.state.offered_sell_kWh[time_slot])
        return (
            offer_arguments["energy"] <=
            self.state.energy_to_sell_dict[time_slot])

    def _offer_impl(self, arguments, response_channel):
        try:
            offer_arguments = {
                k: v for k, v in arguments.items() if k not in ["transaction_id", "time_slot"]}

            replace_existing = offer_arguments.pop("replace_existing", True)
            market = self._get_market_from_command_argument(arguments)
            assert self.can_offer_be_posted(market.time_slot, arguments)
            offer = self.post_offer(
                market, replace_existing=replace_existing, **offer_arguments)

            self.state.reset_offered_sell_energy(
                self.offers.open_offer_energy(market.id), market.time_slot)

            self.redis.publish_json(
                response_channel,
                {"command": "offer", "status": "ready",
                 "market_type": market.type_name,
                 "offer": offer.to_json_string(),
                 "transaction_id": arguments.get("transaction_id")})
        except Exception:
            logging.exception("Error when handling offer create on area %s: Offer Arguments: %s",
                              self.device.name, arguments)
            self.redis.publish_json(
                response_channel,
                {"command": "offer", "status": "error",
                 "market_type": market.type_name,
                 "error_message": f"Error when handling offer create "
                                  f"on area {self.device.name} with arguments {arguments}.",
                 "transaction_id": arguments.get("transaction_id")})

    def list_bids(self, payload: Dict) -> None:
        """Callback for list bids Redis endpoint."""
        self._get_transaction_id(payload)
        response_channel = self.channel_names.list_bids_response
        if not ExternalStrategyConnectionManager.check_for_connected_and_reply(
                self.redis, response_channel, self.connected):
            return
        arguments = json.loads(payload["data"])
        self.pending_requests.append(
            IncomingRequest("list_bids", arguments, response_channel))

    def _list_bids_impl(self, arguments, response_channel):
        try:
            market = self._get_market_from_command_argument(arguments)
            response = {"command": "list_bids", "status": "ready",
                        "bid_list": self.filtered_market_bids(market),
                        "transaction_id": arguments.get("transaction_id")}
        except Exception:
            logging.exception("Error when handling list bids on area %s", self.device.name)
            response = {"command": "list_bids", "status": "error",
                        "error_message": f"Error when listing bids on area {self.device.name}.",
                        "transaction_id": arguments.get("transaction_id")}
        self.redis.publish_json(response_channel, response)

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

    def _delete_bid_impl(self, arguments, response_channel):
        try:
            market = self._get_market_from_command_argument(arguments)
            to_delete_bid_id = arguments.get("bid")
            deleted_bids = self.remove_bid_from_pending(market.id, bid_id=to_delete_bid_id)
            self.state.reset_offered_buy_energy(self.posted_bid_energy(market.id),
                                                market.time_slot)
            self.redis.publish_json(
                response_channel,
                {"command": "bid_delete", "status": "ready", "deleted_bids": deleted_bids,
                 "transaction_id": arguments.get("transaction_id")})
        except Exception:
            logging.exception("Error when handling bid delete on area %s: Bid Arguments: %s",
                              self.device.name, arguments)
            self.redis.publish_json(
                response_channel,
                {"command": "bid_delete", "status": "error",
                 "error_message": "Error when handling bid delete "
                                  f"on area {self.device.name} with arguments {arguments}.",
                 "transaction_id": arguments.get("transaction_id")})

    def bid(self, payload: Dict) -> None:
        """Callback for bid Redis endpoint."""
        transaction_id = self._get_transaction_id(payload)
        required_args = {"price", "energy", "transaction_id"}
        allowed_args = required_args.union({"replace_existing",
                                            "time_slot",
                                            "attributes",
                                            "requirements"})

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

        except Exception:
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

    def _can_bid_be_posted(self, time_slot: DateTime, bid_arguments: Dict) -> bool:
        """Check that the energy being bid is <= than the energy available to be bought."""
        # TODO: Should be removed within D3ASIM-3671
        replace_existing = bid_arguments.get("replace_existing", True)
        if replace_existing:
            # Do not consider previously bid energy, since those bids would be deleted
            return (
                bid_arguments["energy"] <=
                self.state.energy_to_buy_dict[time_slot] +
                self.state.offered_buy_kWh[time_slot])
        return bid_arguments["energy"] <= self.state.energy_to_buy_dict[time_slot]

    def _bid_impl(self, arguments: Dict, bid_response_channel: str) -> None:
        """Implementation for the bid callback, post the bid in the market."""
        try:
            response_message = ""
            arguments, filtered_fields = self.filter_degrees_of_freedom_arguments(arguments)
            if filtered_fields:
                response_message = (
                    "The following arguments are not supported for this market and have been "
                    f"removed from your order: {filtered_fields}.")

            replace_existing = arguments.get("replace_existing", True)
            market = self._get_market_from_command_argument(arguments)
            assert self._can_bid_be_posted(market.time_slot, **arguments)
            bid = self.post_bid(
                market,
                arguments["price"],
                arguments["energy"],
                replace_existing=replace_existing
            )
            self.state.reset_offered_buy_energy(self.posted_bid_energy(market.id),
                                                market.time_slot)
            response = {
                "command": "bid",
                "status": "ready",
                "bid": bid.to_json_string(),
                "market_type": market.type_name,
                "transaction_id": arguments.get("transaction_id"),
                "message": response_message}
        except Exception:
            logging.exception("Error when handling bid create on area %s: Bid Arguments: %s",
                              self.device.name, arguments)
            response = {"command": "bid", "status": "error",
                        "market_type": market.type_name,
                        "error_message": "Error when handling bid create "
                                         f"on area {self.device.name} with arguments {arguments}.",
                        "transaction_id": arguments.get("transaction_id")}

        self.redis.publish_json(bid_response_channel, response)

    @property
    def _device_info_dict(self) -> Dict:
        """Return the asset info."""
        return {
            **super()._device_info_dict,
            **self.state.to_dict(self.spot_market.time_slot),
            "energy_traded": self.energy_traded(self.spot_market.id),
            "total_cost": self.energy_traded_costs(self.spot_market.id),
        }

    def event_market_cycle(self) -> None:
        """Handler for the market cycle event."""
        self._reject_all_pending_requests()
        self._update_connection_status()
        if not self.should_use_default_strategy:
            self.state.add_default_values_to_state_profiles([
                self.spot_market_time_slot, *self.area.future_market_time_slots])
            self._cycle_state()

            if not self.is_aggregator_controlled:
                self.populate_market_info_to_connected_user()
            self._delete_past_state()
        else:
            super().event_market_cycle()

    def event_tick(self) -> None:
        """Process aggregator requests on market tick. Extends super implementation.

        This method is triggered by the TICK event.
        """
        if not self.connected and not self.is_aggregator_controlled:
            super().event_tick()
        else:
            self.state.check_state(self.spot_market.time_slot)

            while self.pending_requests:
                # We want to process requests as First-In-First-Out, so we use popleft
                req = self.pending_requests.popleft()
                self._incoming_commands_callback_selection(req)
            self._dispatch_event_tick_to_external_agent()

    def _incoming_commands_callback_selection(self, req: IncomingRequest) -> None:
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

    def _delete_offer_aggregator(self, arguments: Dict) -> Dict:
        market = self._get_market_from_command_argument(arguments)
        if arguments.get("offer") and not self.offers.is_offer_posted(
                market.id, arguments["offer"]):
            raise Exception("Offer_id is not associated with any posted offer.")

        try:
            market = self._get_market_from_command_argument(arguments)
            to_delete_offer_id = arguments.get("offer")
            deleted_offers = self.offers.remove_offer_from_cache_and_market(
                market, to_delete_offer_id)

            self.state.reset_offered_sell_energy(
                self.offers.open_offer_energy(market.id), market.time_slot)

            response = {
                "command": "offer_delete", "status": "ready",
                "deleted_offers": deleted_offers,
                "area_uuid": self.device.uuid,
                "transaction_id": arguments.get("transaction_id")
            }
        except Exception:
            response = {
                "command": "offer_delete", "status": "error",
                "area_uuid": self.device.uuid,
                "error_message": f"Error when handling offer delete "
                                 f"on area {self.device.name} with arguments {arguments}.",
                "transaction_id": arguments.get("transaction_id")}
        return response

    def _list_offers_aggregator(self, arguments: Dict) -> Dict:
        try:
            market = self._get_market_from_command_argument(arguments)
            filtered_offers = [{"id": v.id, "price": v.price, "energy": v.energy}
                               for _, v in market.get_offers().items()
                               if v.seller == self.device.name]
            response = {
                "command": "list_offers", "status": "ready", "offer_list": filtered_offers,
                "area_uuid": self.device.uuid,
                "transaction_id": arguments.get("transaction_id")}
        except Exception:
            response = {
                "command": "list_offers", "status": "error",
                "area_uuid": self.device.uuid,
                "error_message": f"Error when listing offers on area {self.device.name}.",
                "transaction_id": arguments.get("transaction_id")}
        return response

    def _offer_aggregator(self, arguments: Dict) -> Dict:
        response_message = ""
        arguments, filtered_fields = self.filter_degrees_of_freedom_arguments(arguments)
        if filtered_fields:
            response_message = (
                "The following arguments are not supported for this market and have been "
                f"removed from your order: {filtered_fields}.")

        required_args = {"price", "energy", "type", "transaction_id"}
        allowed_args = required_args.union({"replace_existing",
                                            "time_slot",
                                            "attributes",
                                            "requirements"})

        try:
            # Check that all required arguments have been provided
            assert all(arg in arguments.keys() for arg in required_args)
            # Check that every provided argument is allowed
            assert all(arg in allowed_args for arg in arguments.keys())
            market = self._get_market_from_command_argument(arguments)
            time_slot = market.time_slot if market.time_slot else str_to_pendulum_datetime(
                arguments["time_slot"])

            offer_arguments = {
                k: v for k, v in arguments.items()
                if k not in ["transaction_id", "type"]}

            assert self.can_offer_be_posted(time_slot, offer_arguments)

            replace_existing = offer_arguments.pop("replace_existing", True)

            offer = self.post_offer(
                market, replace_existing=replace_existing, **offer_arguments)

            self.state.reset_offered_sell_energy(
                self.offers.open_offer_energy(market.id), time_slot)

            response = {
                "command": "offer",
                "area_uuid": self.device.uuid,
                "market_type": market.type_name,
                "status": "ready",
                "offer": offer.to_json_string(),
                "transaction_id": arguments.get("transaction_id"),
                "message": response_message}
        except Exception:
            response = {
                "command": "offer", "status": "error",
                "market_type": market.type_name,
                "area_uuid": self.device.uuid,
                "error_message": "Error when handling offer create "
                                 f"on area {self.device.name} with arguments {arguments}.",
                "transaction_id": arguments.get("transaction_id")}
        return response

    def _bid_aggregator(self, arguments: Dict) -> Dict:
        response_message = ""
        arguments, filtered_fields = self.filter_degrees_of_freedom_arguments(arguments)
        if filtered_fields:
            response_message = (
                "The following arguments are not supported for this market and have been "
                f"removed from your order: {filtered_fields}.")

        required_args = {"price", "energy", "type", "transaction_id"}
        allowed_args = required_args.union({"replace_existing",
                                            "time_slot",
                                            "attributes",
                                            "requirements"})

        try:
            # Check that all required arguments have been provided
            assert all(arg in arguments.keys() for arg in required_args)
            # Check that every provided argument is allowed
            assert all(arg in allowed_args for arg in arguments.keys())

            market = self._get_market_from_command_argument(arguments)
            time_slot = market.time_slot if market.time_slot else str_to_pendulum_datetime(
                arguments["time_slot"])

            assert self._can_bid_be_posted(time_slot, arguments)

            replace_existing = arguments.pop("replace_existing", True)
            bid = self.post_bid(
                market,
                arguments["price"],
                arguments["energy"],
                replace_existing=replace_existing,
                time_slot=time_slot
            )

            self.state.reset_offered_buy_energy(
                self.posted_bid_energy(market.id), time_slot)
            response = {
                "command": "bid", "status": "ready",
                "bid": bid.to_json_string(),
                "market_type": market.type_name,
                "area_uuid": self.device.uuid,
                "transaction_id": arguments.get("transaction_id"),
                "message": response_message}
        except Exception:
            response = {
                "command": "bid", "status": "error",
                "market_type": market.type_name,
                "area_uuid": self.device.uuid,
                "error_message": "Error when handling bid create "
                                 f"on area {self.device.name} with arguments {arguments}.",
                "transaction_id": arguments.get("transaction_id")}
        return response

    def _delete_bid_aggregator(self, arguments: Dict) -> Dict:
        """Callback for the delete bid endpoint when sent by aggregator."""
        market = self._get_market_from_command_argument(arguments)
        if arguments.get("bid") and not self.is_bid_posted(market, arguments["bid"]):
            return {
                "command": "bid_delete", "status": "error",
                "error_message": "Bid_id is not associated with any posted bid.",
                "area_uuid": self.device.uuid,
                "transaction_id": arguments.get("transaction_id")}
        try:
            to_delete_bid_id = arguments.get("bid")
            deleted_bids = self.remove_bid_from_pending(market.id, bid_id=to_delete_bid_id)
            self.state.reset_offered_buy_energy(
                self.posted_bid_energy(market.id), market.time_slot)
            response = {
                "command": "bid_delete", "status": "ready", "deleted_bids": deleted_bids,
                "area_uuid": self.device.uuid,
                "transaction_id": arguments.get("transaction_id")}
        except Exception:
            response = {
                "command": "bid_delete", "status": "error",
                "area_uuid": self.device.uuid,
                "error_message": "Error when handling bid delete "
                                 f"on area {self.device.name} with arguments {arguments}.",
                "transaction_id": arguments.get("transaction_id")}
        return response

    def _list_bids_aggregator(self, arguments: Dict) -> Dict:
        """Callback for the list bids endpoint when sent by aggregator."""
        try:
            market = self._get_market_from_command_argument(arguments)
            response = {
                "command": "list_bids", "status": "ready",
                "bid_list": self.filtered_market_bids(market),
                "area_uuid": self.device.uuid,
                "transaction_id": arguments.get("transaction_id")}
        except Exception:
            logging.exception("Error when handling list bids on area %s", self.device.name)
            response = {
                "command": "list_bids", "status": "error",
                "area_uuid": self.device.uuid,
                "error_message": f"Error when listing bids on area {self.device.name}.",
                "transaction_id": arguments.get("transaction_id")}
        return response


class StorageExternalStrategy(StorageExternalMixin, StorageStrategy):
    """Strategy class for external Storage devices."""
