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
import json
import logging
from typing import Dict, List

from pendulum import DateTime

from d3a.d3a_core.util import get_market_maker_rate_from_config
from d3a.models.market import Market
from d3a.models.strategy.external_strategies import (
    ExternalMixin, IncomingRequest, ExternalStrategyConnectionManager, default_market_info)
from d3a.models.strategy.storage import StorageStrategy


class StorageExternalMixin(ExternalMixin):
    """
    Mixin for enabling an external api for the storage strategies.
    Should always be inherited together with a superclass of StorageStrategy.
    """

    def filtered_market_bids(self, market: Market) -> List[Dict]:
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

    def event_activate(self, **kwargs) -> None:
        """Activate the device."""
        super().event_activate(**kwargs)
        self.redis.sub_to_multiple_channels({
            **super().channel_dict,
            f"{self.channel_prefix}/offer": self.offer,
            f"{self.channel_prefix}/delete_offer": self.delete_offer,
            f"{self.channel_prefix}/list_offers": self.list_offers,
            f"{self.channel_prefix}/bid": self.bid,
            f"{self.channel_prefix}/delete_bid": self.delete_bid,
            f"{self.channel_prefix}/list_bids": self.list_bids,
        })

    def list_offers(self, payload: Dict) -> None:
        """Callback for list offers Redis endpoint."""
        self._get_transaction_id(payload)
        list_offers_response_channel = f"{self.channel_prefix}/response/list_offers"
        if not ExternalStrategyConnectionManager.check_for_connected_and_reply(
                self.redis, list_offers_response_channel, self.connected):
            return
        arguments = json.loads(payload["data"])
        self.pending_requests.append(
            IncomingRequest("list_offers", arguments, list_offers_response_channel))

    def _list_offers_impl(self, arguments: Dict, response_channel: str) -> None:
        """Implementation for the list_offers callback, publish this device offers."""
        try:
            market = self._get_market_from_command_argument(arguments)
            filtered_offers = [{"id": v.id, "price": v.price, "energy": v.energy}
                               for _, v in market.get_offers().items()
                               if v.seller == self.device.name]
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
        except Exception:
            logging.exception("Error when handling delete offer request. Payload %s", payload)
            self.redis.publish_json(
                delete_offer_response_channel,
                {"command": "offer_delete",
                 "error": "Incorrect delete offer request. Available parameters: (offer).",
                 "transaction_id": transaction_id})
        else:
            self.pending_requests.append(
                IncomingRequest("delete_offer", arguments, delete_offer_response_channel))

    def _delete_offer_impl(self, arguments: Dict, response_channel: str) -> None:
        """Implementation for the delete_offer callback, delete the received offer from market."""
        try:
            market = self._get_market_from_command_argument(arguments)
            to_delete_offer_id = arguments.get("offer")
            deleted_offers = self.offers.remove_offer_from_cache_and_market(
                market, to_delete_offer_id)
            self.state.offered_sell_kWh[market.time_slot] = (
                self.offers.open_offer_energy(market.id))
            self.state.clamp_energy_to_sell_kWh([market.time_slot])
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

        except Exception:
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

            self.state.offered_sell_kWh[market.time_slot] = (
                self.offers.open_offer_energy(market.id))
            self.state.clamp_energy_to_sell_kWh([market.time_slot])

            self.redis.publish_json(
                response_channel,
                {"command": "offer", "status": "ready",
                 "offer": offer.to_json_string(replace_existing=replace_existing),
                 "transaction_id": arguments.get("transaction_id")})
        except Exception:
            logging.exception("Error when handling offer create on area %s: Offer Arguments: %s",
                              self.device.name, arguments)
            self.redis.publish_json(
                response_channel,
                {"command": "offer", "status": "error",
                 "error_message": f"Error when handling offer create "
                                  f"on area {self.device.name} with arguments {arguments}.",
                 "transaction_id": arguments.get("transaction_id")})

    def list_bids(self, payload: Dict) -> None:
        """Callback for list bids Redis endpoint."""
        self._get_transaction_id(payload)
        list_bids_response_channel = f"{self.channel_prefix}/response/list_bids"
        if not ExternalStrategyConnectionManager.check_for_connected_and_reply(
                self.redis, list_bids_response_channel, self.connected):
            return
        arguments = json.loads(payload["data"])
        self.pending_requests.append(
            IncomingRequest("list_bids", arguments, list_bids_response_channel))

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

    def _delete_bid_impl(self, arguments, response_channel):
        try:
            market = self._get_market_from_command_argument(arguments)
            to_delete_bid_id = arguments.get("bid")
            deleted_bids = self.remove_bid_from_pending(market.id, bid_id=to_delete_bid_id)
            self.state.offered_buy_kWh[market.time_slot] = self.posted_bid_energy(market.id)
            self.state.clamp_energy_to_buy_kWh([market.time_slot])
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

        except Exception:
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
            replace_existing = arguments.get("replace_existing", True)
            market = self._get_market_from_command_argument(arguments)
            assert self._can_bid_be_posted(market.time_slot, **arguments)
            bid = self.post_bid(
                market,
                arguments["price"],
                arguments["energy"],
                replace_existing=replace_existing,
                attributes=arguments.get("attributes"),
                requirements=arguments.get("requirements")
            )
            self.state.offered_buy_kWh[market.time_slot] = self.posted_bid_energy(market.id)
            self.state.clamp_energy_to_buy_kWh([market.time_slot])
            response = {
                "command": "bid", "status": "ready",
                "bid": bid.to_json_string(replace_existing=replace_existing),
                "transaction_id": arguments.get("transaction_id")}
        except Exception:
            logging.exception("Error when handling bid create on area %s: Bid Arguments: %s",
                              self.device.name, arguments)
            response = {"command": "bid", "status": "error",
                        "error_message": "Error when handling bid create "
                                         f"on area {self.device.name} with arguments {arguments}.",
                        "transaction_id": arguments.get("transaction_id")}

        self.redis.publish_json(bid_response_channel, response)

    @property
    def _device_info_dict(self) -> Dict:
        """Return the asset info."""
        return {
            **super()._device_info_dict,
            "energy_to_sell": self.state.energy_to_sell_dict[self.spot_market.time_slot],
            "energy_active_in_bids": self.state.offered_sell_kWh[self.spot_market.time_slot],
            "energy_to_buy": self.state.energy_to_buy_dict[self.spot_market.time_slot],
            "energy_active_in_offers": self.state.offered_buy_kWh[self.spot_market.time_slot],
            "free_storage": self.state.free_storage(self.spot_market.time_slot),
            "used_storage": self.state.used_storage,
            "energy_traded": self.energy_traded(self.spot_market.id),
            "total_cost": self.energy_traded_costs(self.spot_market.id),
        }

    def event_market_cycle(self) -> None:
        """Handler for the market cycle event."""
        self._reject_all_pending_requests()
        self._update_connection_status()
        if not self.should_use_default_strategy:
            self.state.market_cycle(
                self.area.current_market.time_slot
                if self.area.current_market else None,
                self.spot_market.time_slot,
                [self.spot_market_time_slot]
            )
            self.state.clamp_energy_to_sell_kWh([self.spot_market.time_slot])
            self.state.clamp_energy_to_buy_kWh([self.spot_market.time_slot])
            if not self.is_aggregator_controlled:
                market_event_channel = f"{self.channel_prefix}/events/market"
                market_info = self.spot_market.info
                if self.is_aggregator_controlled:
                    market_info.update(default_market_info)
                market_info["device_info"] = self._device_info_dict
                market_info["event"] = "market"
                market_info["device_bill"] = self.device.stats.aggregated_stats.get("bills")
                market_info["area_uuid"] = self.device.uuid
                market_info["last_market_maker_rate"] = (
                    get_market_maker_rate_from_config(self.area.current_market))
                market_info["last_market_stats"] = (
                    self.market_area.stats.get_price_stats_current_market())
                self.redis.publish_json(market_event_channel, market_info)
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
            self.state.tick(self.market_area, self.spot_market.time_slot)
            self.state.clamp_energy_to_sell_kWh([self.spot_market.time_slot])
            self.state.clamp_energy_to_buy_kWh([self.spot_market.time_slot])

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
            self.state.offered_sell_kWh[market.time_slot] = (
                self.offers.open_offer_energy(market.id))
            self.state.clamp_energy_to_sell_kWh([market.time_slot])
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
        required_args = {"price", "energy", "type", "transaction_id"}
        allowed_args = required_args.union({"replace_existing",
                                            "time_slot",
                                            "attributes",
                                            "requirements"})

        with self._lock:
            try:
                # Check that all required arguments have been provided
                assert all(arg in arguments.keys() for arg in required_args)
                # Check that every provided argument is allowed
                assert all(arg in allowed_args for arg in arguments.keys())
                market = self._get_market_from_command_argument(arguments)

                offer_arguments = {
                    k: v for k, v in arguments.items()
                    if k not in ["transaction_id", "type", "time_slot"]}

                assert self.can_offer_be_posted(market.time_slot, offer_arguments)

                replace_existing = offer_arguments.pop("replace_existing", True)

                offer = self.post_offer(
                    market, replace_existing=replace_existing, **offer_arguments)

                self.state.offered_sell_kWh[market.time_slot] = (
                    self.offers.open_offer_energy(market.id))
                self.state.clamp_energy_to_sell_kWh([market.time_slot])

                response = {
                    "command": "offer",
                    "area_uuid": self.device.uuid,
                    "status": "ready",
                    "offer": offer.to_json_string(replace_existing=replace_existing),
                    "transaction_id": arguments.get("transaction_id"),
                }
            except Exception:
                response = {
                    "command": "offer", "status": "error",
                    "area_uuid": self.device.uuid,
                    "error_message": "Error when handling offer create "
                                     f"on area {self.device.name} with arguments {arguments}.",
                    "transaction_id": arguments.get("transaction_id")}
            return response

    def _bid_aggregator(self, arguments: Dict) -> Dict:
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
            assert self._can_bid_be_posted(market.time_slot, arguments)

            replace_existing = arguments.pop("replace_existing", True)
            bid = self.post_bid(
                market,
                arguments["price"],
                arguments["energy"],
                replace_existing=replace_existing,
                attributes=arguments.get("attributes"),
                requirements=arguments.get("requirements")
            )

            self.state.offered_buy_kWh[market.time_slot] = self.posted_bid_energy(market.id)
            self.state.clamp_energy_to_buy_kWh([market.time_slot])
            response = {
                "command": "bid", "status": "ready",
                "bid": bid.to_json_string(replace_existing=replace_existing),
                "area_uuid": self.device.uuid,
                "transaction_id": arguments.get("transaction_id")}
        except Exception:
            response = {
                "command": "bid", "status": "error",
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
            self.state.offered_buy_kWh[market.time_slot] = self.posted_bid_energy(market.id)
            self.state.clamp_energy_to_buy_kWh([market.time_slot])
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
