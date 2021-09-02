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
from typing import List, Dict

from d3a.models.strategy.external_strategies import IncomingRequest, default_market_info
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.strategy.external_strategies import ExternalMixin, check_for_connected_and_reply
from d3a.d3a_core.util import get_market_maker_rate_from_config


class StorageExternalMixin(ExternalMixin):
    """
    Mixin for enabling an external api for the storage strategies.
    Should always be inherited together with a superclass of StorageStrategy.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def filtered_market_bids(self, market) -> List[Dict]:
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

    def event_activate(self, **kwargs):
        super().event_activate(**kwargs)
        self.redis.sub_to_multiple_channels({
            **super().channel_dict,
            f'{self.channel_prefix}/offer': self.offer,
            f'{self.channel_prefix}/delete_offer': self.delete_offer,
            f'{self.channel_prefix}/list_offers': self.list_offers,
            f'{self.channel_prefix}/bid': self.bid,
            f'{self.channel_prefix}/delete_bid': self.delete_bid,
            f'{self.channel_prefix}/list_bids': self.list_bids,
        })

    def list_offers(self, payload):
        self._get_transaction_id(payload)
        list_offers_response_channel = f'{self.channel_prefix}/response/list_offers'
        if not check_for_connected_and_reply(self.redis, list_offers_response_channel,
                                             self.connected):
            return
        arguments = json.loads(payload["data"])
        self.pending_requests.append(
            IncomingRequest("list_offers", arguments, list_offers_response_channel))

    def _list_offers_impl(self, arguments, response_channel):
        try:
            market = self._get_market_from_command_argument(arguments)
            filtered_offers = [{"id": v.id, "price": v.price, "energy": v.energy}
                               for _, v in market.get_offers().items()
                               if v.seller == self.device.name]
            self.redis.publish_json(
                response_channel,
                {"command": "list_offers", "status": "ready", "offer_list": filtered_offers,
                 "transaction_id": arguments.get("transaction_id")})
        except Exception:
            logging.exception(f"Error when handling list offers on area {self.device.name}")
            self.redis.publish_json(
                response_channel,
                {"command": "list_offers", "status": "error",
                 "error_message": f"Error when listing offers on area {self.device.name}.",
                 "transaction_id": arguments.get("transaction_id")})

    def delete_offer(self, payload):
        transaction_id = self._get_transaction_id(payload)
        delete_offer_response_channel = f'{self.channel_prefix}/response/delete_offer'
        if not check_for_connected_and_reply(self.redis, delete_offer_response_channel,
                                             self.connected):
            return
        try:
            arguments = json.loads(payload["data"])
            market = self._get_market_from_command_argument(arguments)
            if ("offer" in arguments and arguments["offer"] is not None) and \
                    not self.offers.is_offer_posted(market.id, arguments["offer"]):
                raise Exception("Offer_id is not associated with any posted offer.")
        except Exception:
            logging.exception(f"Error when handling delete offer request. Payload {payload}")
            self.redis.publish_json(
                delete_offer_response_channel,
                {"command": "offer_delete",
                 "error": "Incorrect delete offer request. Available parameters: (offer).",
                 "transaction_id": transaction_id})
        else:
            self.pending_requests.append(
                IncomingRequest("delete_offer", arguments, delete_offer_response_channel))

    def _delete_offer_impl(self, arguments, response_channel):
        try:
            market = self._get_market_from_command_argument(arguments)
            to_delete_offer_id = arguments["offer"] if "offer" in arguments else None
            deleted_offers = \
                self.offers.remove_offer_from_cache_and_market(
                    market, to_delete_offer_id)
            self.state.offered_sell_kWh[market.time_slot] = \
                self.offers.open_offer_energy(market.id)
            self.state.clamp_energy_to_sell_kWh([market.time_slot])
            self.redis.publish_json(
                response_channel,
                {"command": "offer_delete", "status": "ready",
                 "deleted_offers": deleted_offers,
                 "transaction_id": arguments.get("transaction_id")})
        except Exception:
            logging.exception(f"Error when handling offer delete on area {self.device.name}: "
                              f"Offer Arguments: {arguments}")
            self.redis.publish_json(
                response_channel,
                {"command": "offer_delete", "status": "error",
                 "error_message": f"Error when handling offer delete "
                                  f"on area {self.device.name} with arguments {arguments}.",
                 "transaction_id": arguments.get("transaction_id")})

    def offer(self, payload):
        transaction_id = self._get_transaction_id(payload)
        required_args = {"price", "energy", "transaction_id"}
        allowed_args = required_args.union({"replace_existing",
                                            "timeslot",
                                            "attributes",
                                            "requirements"})

        offer_response_channel = f"{self.channel_prefix}/response/offer"
        if not check_for_connected_and_reply(self.redis, offer_response_channel,
                                             self.connected):
            return
        try:
            arguments = json.loads(payload["data"])

            # Check that all required arguments have been provided
            assert all(arg in arguments.keys() for arg in required_args)
            # Check that every provided argument is allowed
            assert all(arg in allowed_args for arg in arguments.keys())

        except Exception:
            logging.exception(f"Incorrect offer request. Payload {payload}.")
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

    def can_offer_be_posted(self, time_slot, **offer_arguments):
        """Check that the energy being offered is <= than the energy available to be sold."""

        replace_existing = offer_arguments.get("replace_existing", True)
        if replace_existing:
            # Do not consider previously offered energy, since those offers would be deleted
            return (
                offer_arguments["energy"] <=
                self.state.energy_to_sell_dict[time_slot] +
                self.state.offered_sell_kWh[time_slot])
        else:
            return (
                offer_arguments["energy"] <=
                self.state.energy_to_sell_dict[time_slot])

    def _offer_impl(self, arguments, response_channel):
        try:
            offer_arguments = {k: v for k, v in arguments.items() if not k == "transaction_id"}

            replace_existing = offer_arguments.pop("replace_existing", True)
            market = self._get_market_from_command_argument(arguments)
            assert self.can_offer_be_posted(market.time_slot, **arguments)
            offer = self.post_offer(
                market, replace_existing=replace_existing, **offer_arguments)

            self.state.offered_sell_kWh[market.time_slot] = \
                self.offers.open_offer_energy(market.id)
            self.state.clamp_energy_to_sell_kWh([market.time_slot])

            self.redis.publish_json(
                response_channel,
                {"command": "offer", "status": "ready",
                 "offer": offer.to_json_string(replace_existing=replace_existing),
                 "transaction_id": arguments.get("transaction_id")})
        except Exception:
            logging.exception(f"Error when handling offer create on area {self.device.name}: "
                              f"Offer Arguments: {arguments}")
            self.redis.publish_json(
                response_channel,
                {"command": "offer", "status": "error",
                 "error_message": f"Error when handling offer create "
                                  f"on area {self.device.name} with arguments {arguments}.",
                 "transaction_id": arguments.get("transaction_id")})

    def list_bids(self, payload):
        self._get_transaction_id(payload)
        list_bids_response_channel = f"{self.channel_prefix}/response/list_bids"
        if not check_for_connected_and_reply(self.redis, list_bids_response_channel,
                                             self.connected):
            return
        arguments = json.loads(payload["data"])
        self.pending_requests.append(
            IncomingRequest("list_bids", arguments, list_bids_response_channel))

    def _list_bids_impl(self, arguments, response_channel):
        try:
            market = self._get_market_from_command_argument(arguments)
            self.redis.publish_json(
                response_channel, {
                    "command": "list_bids", "status": "ready",
                    "bid_list": self.filtered_market_bids(market),
                    "transaction_id": arguments.get("transaction_id")})
        except Exception:
            logging.exception(f"Error when handling list bids on area {self.device.name}")
            self.redis.publish_json(
                response_channel,
                {"command": "list_bids", "status": "error",
                 "error_message": f"Error when listing bids on area {self.device.name}.",
                 "transaction_id": arguments.get("transaction_id")})

    def delete_bid(self, payload):
        transaction_id = self._get_transaction_id(payload)
        delete_bid_response_channel = f"{self.channel_prefix}/response/delete_bid"
        if not check_for_connected_and_reply(self.redis,
                                             delete_bid_response_channel, self.connected):
            return
        try:
            arguments = json.loads(payload["data"])
            market = self._get_market_from_command_argument(arguments)
            if ("bid" in arguments and arguments["bid"] is not None) and \
                    not self.is_bid_posted(market, arguments["bid"]):
                raise Exception("Bid_id is not associated with any posted bid.")
        except Exception as e:
            self.redis.publish_json(
                delete_bid_response_channel,
                {"command": "bid_delete",
                 "error": f"Incorrect delete bid request. Available parameters: (bid)."
                          f"Exception: {str(e)}",
                 "transaction_id": transaction_id}
            )
        else:
            self.pending_requests.append(
                IncomingRequest("delete_bid", arguments, delete_bid_response_channel))

    def _delete_bid_impl(self, arguments, response_channel):
        try:
            market = self._get_market_from_command_argument(arguments)
            to_delete_bid_id = arguments["bid"] if "bid" in arguments else None
            deleted_bids = \
                self.remove_bid_from_pending(market.id, bid_id=to_delete_bid_id)
            self.state.offered_buy_kWh[market.time_slot] = \
                self.posted_bid_energy(market.id)
            self.state.clamp_energy_to_buy_kWh([market.time_slot])
            self.redis.publish_json(
                response_channel,
                {"command": "bid_delete", "status": "ready", "deleted_bids": deleted_bids,
                 "transaction_id": arguments.get("transaction_id")})
        except Exception:
            logging.exception(f"Error when handling bid delete on area {self.device.name}: "
                              f"Bid Arguments: {arguments}")
            self.redis.publish_json(
                response_channel,
                {"command": "bid_delete", "status": "error",
                 "error_message": f"Error when handling bid delete "
                                  f"on area {self.device.name} with arguments {arguments}.",
                 "transaction_id": arguments.get("transaction_id")})

    def bid(self, payload):
        transaction_id = self._get_transaction_id(payload)
        required_args = {"price", "energy", "transaction_id"}
        allowed_args = required_args.union({"replace_existing",
                                            "timeslot",
                                            "attributes",
                                            "requirements"})

        bid_response_channel = f"{self.channel_prefix}/response/bid"
        if not check_for_connected_and_reply(self.redis, bid_response_channel, self.connected):
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

    def can_bid_be_posted(self, time_slot, **bid_arguments):
        """Check that the energy being bid is <= than the energy available to be bought."""

        replace_existing = bid_arguments.get("replace_existing", True)
        if replace_existing:
            # Do not consider previously bid energy, since those bids would be deleted
            return (
                bid_arguments["energy"] <=
                self.state.energy_to_buy_dict[time_slot] +
                self.state.offered_buy_kWh[time_slot])
        else:
            return bid_arguments["energy"] <= self.state.energy_to_buy_dict[time_slot]

    def _bid_impl(self, arguments, bid_response_channel):
        try:
            replace_existing = arguments.get("replace_existing", True)
            market = self._get_market_from_command_argument(arguments)
            assert self.can_bid_be_posted(market.time_slot, **arguments)
            bid = self.post_bid(
                market,
                arguments["price"],
                arguments["energy"],
                replace_existing=replace_existing,
                attributes=arguments.get("attributes"),
                requirements=arguments.get("requirements")
            )
            self.state.offered_buy_kWh[market.time_slot] = \
                self.posted_bid_energy(market.id)
            self.state.clamp_energy_to_buy_kWh([market.time_slot])
            self.redis.publish_json(
                bid_response_channel, {
                    "command": "bid", "status": "ready",
                    "bid": bid.to_json_string(replace_existing=replace_existing),
                    "transaction_id": arguments.get("transaction_id")})
        except Exception:
            logging.exception(f"Error when handling bid create on area {self.device.name}: "
                              f"Bid Arguments: {arguments}")
            self.redis.publish_json(
                bid_response_channel,
                {"command": "bid", "status": "error",
                 "error_message": f"Error when handling bid create "
                                  f"on area {self.device.name} with arguments {arguments}.",
                 "transaction_id": arguments.get("transaction_id")})

    @property
    def _device_info_dict(self):
        return {
            "energy_to_sell": self.state.energy_to_sell_dict[self.next_market.time_slot],
            "energy_active_in_bids": self.state.offered_sell_kWh[self.next_market.time_slot],
            "energy_to_buy": self.state.energy_to_buy_dict[self.next_market.time_slot],
            "energy_active_in_offers": self.state.offered_buy_kWh[self.next_market.time_slot],
            "free_storage": self.state.free_storage(self.next_market.time_slot),
            "used_storage": self.state.used_storage,
            "energy_traded": self.energy_traded(self.next_market.id),
            "total_cost": self.energy_traded_costs(self.next_market.id),
        }

    def event_market_cycle(self):
        self._reject_all_pending_requests()
        self.register_on_market_cycle()
        if not self.should_use_default_strategy:
            self.state.market_cycle(
                self.market_area.current_market.time_slot
                if self.market_area.current_market else None,
                self.next_market.time_slot,
                self.future_markets_time_slots
            )
            self.state.clamp_energy_to_sell_kWh([self.next_market.time_slot])
            self.state.clamp_energy_to_buy_kWh([self.next_market.time_slot])
            if not self.is_aggregator_controlled:
                market_event_channel = f"{self.channel_prefix}/events/market"
                market_info = self.next_market.info
                if self.is_aggregator_controlled:
                    market_info.update(default_market_info)
                market_info["device_info"] = self._device_info_dict
                market_info["event"] = "market"
                market_info["device_bill"] = self.device.stats.aggregated_stats["bills"] \
                    if "bills" in self.device.stats.aggregated_stats else None
                market_info["area_uuid"] = self.device.uuid
                market_info["last_market_maker_rate"] = (
                    get_market_maker_rate_from_config(self.area.current_market))
                market_info["last_market_stats"] = (
                    self.market_area.stats.get_price_stats_current_market())
                self.redis.publish_json(market_event_channel, market_info)
            self._delete_past_state()
        else:
            super().event_market_cycle()

    def event_tick(self):
        """Process aggregator requests on market tick. Extends super implementation.

        This method is triggered by the TICK event.
        """
        if not self.connected and not self.is_aggregator_controlled:
            super().event_tick()
        else:
            self.state.tick(self.market_area, self.next_market.time_slot)
            self.state.clamp_energy_to_sell_kWh([self.next_market.time_slot])
            self.state.clamp_energy_to_buy_kWh([self.next_market.time_slot])

            while self.pending_requests:
                # We want to process requests as First-In-First-Out, so we use popleft
                req = self.pending_requests.popleft()
                self._incoming_commands_callback_selection(req)
            self._dispatch_event_tick_to_external_agent()

    def _incoming_commands_callback_selection(self, req):
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

    def _delete_offer_aggregator(self, arguments):
        market = self._get_market_from_command_argument(arguments)
        if ("offer" in arguments and arguments["offer"] is not None) and \
                not self.offers.is_offer_posted(market.id, arguments["offer"]):
            raise Exception("Offer_id is not associated with any posted offer.")

        try:
            market = self._get_market_from_command_argument(arguments)
            to_delete_offer_id = arguments["offer"] if "offer" in arguments else None
            deleted_offers = self.offers.remove_offer_from_cache_and_market(
                market, to_delete_offer_id)
            self.state.offered_sell_kWh[market.time_slot] = \
                self.offers.open_offer_energy(market.id)
            self.state.clamp_energy_to_sell_kWh([market.time_slot])
            return {
                "command": "offer_delete", "status": "ready",
                "deleted_offers": deleted_offers,
                "area_uuid": self.device.uuid,
                "transaction_id": arguments.get("transaction_id")
            }
        except Exception:
            return {
                "command": "offer_delete", "status": "error",
                "area_uuid": self.device.uuid,
                "error_message": f"Error when handling offer delete "
                                 f"on area {self.device.name} with arguments {arguments}.",
                "transaction_id": arguments.get("transaction_id")}

    def _list_offers_aggregator(self, arguments):
        try:
            market = self._get_market_from_command_argument(arguments)
            filtered_offers = [{"id": v.id, "price": v.price, "energy": v.energy}
                               for _, v in market.get_offers().items()
                               if v.seller == self.device.name]
            return {
                "command": "list_offers", "status": "ready", "offer_list": filtered_offers,
                "area_uuid": self.device.uuid,
                "transaction_id": arguments.get("transaction_id")}
        except Exception:
            return {
                "command": "list_offers", "status": "error",
                "area_uuid": self.device.uuid,
                "error_message": f"Error when listing offers on area {self.device.name}.",
                "transaction_id": arguments.get("transaction_id")}

    def _offer_aggregator(self, arguments):
        required_args = {"price", "energy", "type", "transaction_id"}
        allowed_args = required_args.union({"replace_existing",
                                            "timeslot",
                                            "attributes",
                                            "requirements"})

        # Check that all required arguments have been provided
        assert all(arg in arguments.keys() for arg in required_args)
        # Check that every provided argument is allowed
        assert all(arg in allowed_args for arg in arguments.keys())
        market = self._get_market_from_command_argument(arguments)

        with self.lock:
            try:
                offer_arguments = {
                    k: v for k, v in arguments.items() if k not in ["transaction_id", "type"]}
                assert self.can_offer_be_posted(market.time_slot, **offer_arguments)

                replace_existing = offer_arguments.pop("replace_existing", True)

                offer = self.post_offer(
                    market, replace_existing=replace_existing, **offer_arguments)

                self.state.offered_sell_kWh[market.time_slot] = \
                    self.offers.open_offer_energy(market.id)
                self.state.clamp_energy_to_sell_kWh([market.time_slot])

                return {
                    "command": "offer",
                    "area_uuid": self.device.uuid,
                    "status": "ready",
                    "offer": offer.to_json_string(replace_existing=replace_existing),
                    "transaction_id": arguments.get("transaction_id"),
                }
            except Exception:
                return {
                    "command": "offer", "status": "error",
                    "area_uuid": self.device.uuid,
                    "error_message": f"Error when handling offer create "
                                     f"on area {self.device.name} with arguments {arguments}.",
                    "transaction_id": arguments.get("transaction_id")}

    def _bid_aggregator(self, arguments: Dict):
        required_args = {"price", "energy", "type", "transaction_id"}
        allowed_args = required_args.union({"replace_existing",
                                            "timeslot",
                                            "attributes",
                                            "requirements"})

        try:
            # Check that all required arguments have been provided
            assert all(arg in arguments.keys() for arg in required_args)
            # Check that every provided argument is allowed
            assert all(arg in allowed_args for arg in arguments.keys())

            market = self._get_market_from_command_argument(arguments)
            assert self.can_bid_be_posted(market.time_slot, **arguments)

            replace_existing = arguments.pop("replace_existing", True)
            bid = self.post_bid(
                market,
                arguments["price"],
                arguments["energy"],
                replace_existing=replace_existing,
                attributes=arguments.get("attributes"),
                requirements=arguments.get("requirements")
            )

            self.state.offered_buy_kWh[market.time_slot] = \
                self.posted_bid_energy(market.id)
            self.state.clamp_energy_to_buy_kWh([market.time_slot])
            return {
                "command": "bid", "status": "ready",
                "bid": bid.to_json_string(replace_existing=replace_existing),
                "area_uuid": self.device.uuid,
                "transaction_id": arguments.get("transaction_id")}
        except Exception:
            return {
                "command": "bid", "status": "error",
                "area_uuid": self.device.uuid,
                "error_message": f"Error when handling bid create "
                                 f"on area {self.device.name} with arguments {arguments}.",
                "transaction_id": arguments.get("transaction_id")}

    def _delete_bid_aggregator(self, arguments):
        market = self._get_market_from_command_argument(arguments)
        if ("bid" in arguments and arguments["bid"] is not None) and \
                not self.is_bid_posted(market, arguments["bid"]):
            return {
                "command": "bid_delete", "status": "error",
                "error_message": "Bid_id is not associated with any posted bid.",
                "area_uuid": self.device.uuid,
                "transaction_id": arguments.get("transaction_id")}
        try:
            to_delete_bid_id = arguments["bid"] if "bid" in arguments else None
            deleted_bids = \
                self.remove_bid_from_pending(market.id, bid_id=to_delete_bid_id)
            self.state.offered_buy_kWh[market.time_slot] = \
                self.posted_bid_energy(market.id)
            self.state.clamp_energy_to_buy_kWh([market.time_slot])
            return {
                "command": "bid_delete", "status": "ready", "deleted_bids": deleted_bids,
                "area_uuid": self.device.uuid,
                "transaction_id": arguments.get("transaction_id")}
        except Exception:
            return {
                "command": "bid_delete", "status": "error",
                "area_uuid": self.device.uuid,
                "error_message": f"Error when handling bid delete "
                                 f"on area {self.device.name} with arguments {arguments}.",
                "transaction_id": arguments.get("transaction_id")}

    def _list_bids_aggregator(self, arguments):
        try:
            market = self._get_market_from_command_argument(arguments)
            return {
                "command": "list_bids", "status": "ready",
                "bid_list": self.filtered_market_bids(market),
                "area_uuid": self.device.uuid,
                "transaction_id": arguments.get("transaction_id")}
        except Exception:
            logging.exception(f"Error when handling list bids on area {self.device.name}")
            return {
                "command": "list_bids", "status": "error",
                "area_uuid": self.device.uuid,
                "error_message": f"Error when listing bids on area {self.device.name}.",
                "transaction_id": arguments.get("transaction_id")}


class StorageExternalStrategy(StorageExternalMixin, StorageStrategy):
    pass
