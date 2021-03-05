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

from d3a.d3a_core.exceptions import MarketException
from d3a.models.strategy.external_strategies import IncomingRequest
from d3a.models.strategy.storage import StorageStrategy
from d3a.models.strategy.external_strategies import ExternalMixin, check_for_connected_and_reply
from d3a.d3a_core.redis_connections.aggregator_connection import default_market_info
from d3a.d3a_core.util import get_current_market_maker_rate


class StorageExternalMixin(ExternalMixin):
    """
    Mixin for enabling an external api for the storage strategies.
    Should always be inherited together with a superclass of StorageStrategy.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @property
    def filtered_bids_next_market(self) -> List[Dict]:
        """Get a representation of each of the device's bids from the next market."""

        return [
            {'id': bid.id, 'price': bid.price, 'energy': bid.energy}
            for _, bid in self.next_market.get_bids().items()
            if bid.buyer == self.device.name]

    def event_activate(self, **kwargs):
        super().event_activate(**kwargs)
        self.redis.sub_to_multiple_channels({
            **super().channel_dict,
            f'{self.channel_prefix}/offer': self._offer,
            f'{self.channel_prefix}/delete_offer': self._delete_offer,
            f'{self.channel_prefix}/list_offers': self._list_offers,
            f'{self.channel_prefix}/bid': self._bid,
            f'{self.channel_prefix}/delete_bid': self._delete_bid,
            f'{self.channel_prefix}/list_bids': self._list_bids,
        })

    def _list_offers(self, payload):
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
            filtered_offers = [{"id": v.id, "price": v.price, "energy": v.energy}
                               for _, v in self.next_market.get_offers().items()
                               if v.seller == self.device.name]
            self.redis.publish_json(
                response_channel,
                {"command": "list_offers", "status": "ready", "offer_list": filtered_offers,
                 "transaction_id": arguments.get("transaction_id", None)})
        except Exception as e:
            logging.error(f"Error when handling list offers on area {self.device.name}: "
                          f"Exception: {str(e)}")
            self.redis.publish_json(
                response_channel,
                {"command": "list_offers", "status": "error",
                 "error_message": f"Error when listing offers on area {self.device.name}.",
                 "transaction_id": arguments.get("transaction_id", None)})

    def _delete_offer(self, payload):
        transaction_id = self._get_transaction_id(payload)
        delete_offer_response_channel = f'{self.channel_prefix}/response/delete_offer'
        if not check_for_connected_and_reply(self.redis, delete_offer_response_channel,
                                             self.connected):
            return
        try:
            arguments = json.loads(payload["data"])
            if ("offer" in arguments and arguments["offer"] is not None) and \
                    not self.offers.is_offer_posted(self.next_market.id, arguments["offer"]):
                raise Exception("Offer_id is not associated with any posted offer.")
        except Exception as e:
            logging.error(f"Error when handling delete offer request. Payload {payload}. "
                          f"Exception {str(e)}.")
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
            to_delete_offer_id = arguments["offer"] if "offer" in arguments else None
            deleted_offers = \
                self.offers.remove_offer_from_cache_and_market(
                    self.next_market, to_delete_offer_id)
            self.state.offered_sell_kWh[self.next_market.time_slot] = \
                self.offers.open_offer_energy(self.next_market.id)
            self.state.clamp_energy_to_sell_kWh([self.next_market.time_slot])
            self.redis.publish_json(
                response_channel,
                {"command": "offer_delete", "status": "ready",
                 "deleted_offers": deleted_offers,
                 "transaction_id": arguments.get("transaction_id", None)})
        except Exception as e:
            logging.error(f"Error when handling offer delete on area {self.device.name}: "
                          f"Exception: {str(e)}, Offer Arguments: {arguments}")
            self.redis.publish_json(
                response_channel,
                {"command": "offer_delete", "status": "error",
                 "error_message": f"Error when handling offer delete "
                                  f"on area {self.device.name} with arguments {arguments}.",
                 "transaction_id": arguments.get("transaction_id", None)})

    def _offer(self, payload):
        transaction_id = self._get_transaction_id(payload)
        required_args = {'price', 'energy', 'transaction_id'}
        allowed_args = required_args.union({'replace_existing'})

        offer_response_channel = f'{self.channel_prefix}/response/offer'
        if not check_for_connected_and_reply(self.redis, offer_response_channel,
                                             self.connected):
            return
        try:
            arguments = json.loads(payload["data"])

            # Check that all required arguments have been provided
            assert all(arg in arguments.keys() for arg in required_args)
            # Check that every provided argument is allowed
            assert all(arg in allowed_args for arg in arguments.keys())

            arguments['seller'] = self.device.name
            arguments['seller_origin'] = self.device.name
        except Exception as e:
            logging.error(f"Incorrect offer request. Payload {payload}. Exception {str(e)}.")
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

        replace_existing = offer_arguments.get('replace_existing', True)
        if replace_existing:
            # Do not consider previously offered energy, since those offers would be deleted
            return (
                offer_arguments['energy'] <=
                self.state.energy_to_sell_dict[time_slot] +
                self.state.offered_sell_kWh[time_slot])
        else:
            return (
                offer_arguments['energy'] <=
                self.state.energy_to_sell_dict[time_slot])

    def _offer_impl(self, arguments, response_channel):
        try:
            offer_arguments = {k: v for k, v in arguments.items() if not k == "transaction_id"}
            assert self.can_offer_be_posted(self.next_market.time_slot, **offer_arguments)

            replace_existing = offer_arguments.pop('replace_existing', True)
            offer = self.post_offer(
                self.next_market, replace_existing=replace_existing, **offer_arguments)

            self.state.offered_sell_kWh[self.next_market.time_slot] = \
                self.offers.open_offer_energy(self.next_market.id)
            self.state.clamp_energy_to_sell_kWh([self.next_market.time_slot])

            self.redis.publish_json(
                response_channel,
                {"command": "offer", "status": "ready",
                 "offer": offer.to_JSON_string(replace_existing=replace_existing),
                 "transaction_id": arguments.get("transaction_id", None)})
        except Exception as e:
            logging.error(f"Error when handling offer create on area {self.device.name}: "
                          f"Exception: {str(e)}, Offer Arguments: {arguments}")
            self.redis.publish_json(
                response_channel,
                {"command": "offer", "status": "error",
                 "error_message": f"Error when handling offer create "
                                  f"on area {self.device.name} with arguments {arguments}.",
                 "transaction_id": arguments.get("transaction_id", None)})

    def _list_bids(self, payload):
        self._get_transaction_id(payload)
        list_bids_response_channel = f'{self.channel_prefix}/response/list_bids'
        if not check_for_connected_and_reply(self.redis, list_bids_response_channel,
                                             self.connected):
            return
        arguments = json.loads(payload["data"])
        self.pending_requests.append(
            IncomingRequest("list_bids", arguments, list_bids_response_channel))

    def _list_bids_impl(self, arguments, response_channel):
        try:
            self.redis.publish_json(
                response_channel, {
                    "command": "list_bids", "status": "ready",
                    "bid_list": self.filtered_bids_next_market,
                    "transaction_id": arguments.get("transaction_id", None)})
        except Exception as e:
            logging.error(f"Error when handling list bids on area {self.device.name}: "
                          f"Exception: {str(e)}")
            self.redis.publish_json(
                response_channel,
                {"command": "list_bids", "status": "error",
                 "error_message": f"Error when listing bids on area {self.device.name}.",
                 "transaction_id": arguments.get("transaction_id", None)})

    def _delete_bid(self, payload):
        transaction_id = self._get_transaction_id(payload)
        delete_bid_response_channel = f'{self.channel_prefix}/response/delete_bid'
        if not check_for_connected_and_reply(self.redis,
                                             delete_bid_response_channel, self.connected):
            return
        try:
            arguments = json.loads(payload["data"])
            if ("bid" in arguments and arguments["bid"] is not None) and \
                    not self.is_bid_posted(self.next_market, arguments["bid"]):
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
            to_delete_bid_id = arguments["bid"] if "bid" in arguments else None
            deleted_bids = \
                self.remove_bid_from_pending(self.next_market.id, bid_id=to_delete_bid_id)
            self.state.offered_buy_kWh[self.next_market.time_slot] = \
                self.posted_bid_energy(self.next_market.id)
            self.state.clamp_energy_to_buy_kWh([self.next_market.time_slot])
            self.redis.publish_json(
                response_channel,
                {"command": "bid_delete", "status": "ready", "deleted_bids": deleted_bids,
                 "transaction_id": arguments.get("transaction_id", None)})
        except Exception as e:
            logging.error(f"Error when handling bid delete on area {self.device.name}: "
                          f"Exception: {str(e)}, Bid Arguments: {arguments}")
            self.redis.publish_json(
                response_channel,
                {"command": "bid_delete", "status": "error",
                 "error_message": f"Error when handling bid delete "
                                  f"on area {self.device.name} with arguments {arguments}.",
                 "transaction_id": arguments.get("transaction_id", None)})

    def _bid(self, payload):
        transaction_id = self._get_transaction_id(payload)
        required_args = {'price', 'energy', 'transaction_id'}
        allowed_args = required_args.union({'replace_existing'})

        bid_response_channel = f'{self.channel_prefix}/response/bid'
        if not check_for_connected_and_reply(self.redis, bid_response_channel, self.connected):
            return
        try:
            arguments = json.loads(payload["data"])

            # Check that all required arguments have been provided
            assert all(arg in arguments.keys() for arg in required_args)
            # Check that every provided argument is allowed
            assert all(arg in allowed_args for arg in arguments.keys())

            arguments['buyer'] = self.device.name
            arguments['buyer_origin'] = self.device.name
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

        replace_existing = bid_arguments.get('replace_existing', True)
        if replace_existing:
            # Do not consider previously bid energy, since those bids would be deleted
            return (
                bid_arguments['energy'] <=
                self.state.energy_to_buy_dict[time_slot] +
                self.state.offered_buy_kWh[time_slot])
        else:
            return bid_arguments['energy'] <= self.state.energy_to_buy_dict[time_slot]

    def _bid_impl(self, arguments, bid_response_channel):
        try:
            assert self.can_bid_be_posted(self.next_market.time_slot, **arguments)

            replace_existing = arguments.get('replace_existing', True)
            bid = self.post_bid(
                self.next_market,
                arguments["price"],
                arguments["energy"],
                replace_existing=replace_existing,
                buyer_origin=arguments["buyer_origin"],
                buyer_origin_id=arguments["buyer_origin_id"]
            )
            self.state.offered_buy_kWh[self.next_market.time_slot] = \
                self.posted_bid_energy(self.next_market.id)
            self.state.clamp_energy_to_buy_kWh([self.next_market.time_slot])
            self.redis.publish_json(
                bid_response_channel, {
                    "command": "bid", "status": "ready",
                    "bid": bid.to_JSON_string(replace_existing=replace_existing),
                    "transaction_id": arguments.get("transaction_id", None)})
        except Exception as e:
            logging.error(f"Error when handling bid create on area {self.device.name}: "
                          f"Exception: {str(e)}, Bid Arguments: {arguments}")
            self.redis.publish_json(
                bid_response_channel,
                {"command": "bid", "status": "error",
                 "error_message": f"Error when handling bid create "
                                  f"on area {self.device.name} with arguments {arguments}.",
                 "transaction_id": arguments.get("transaction_id", None)})

    @property
    def _device_info_dict(self):
        return {
            "energy_to_sell": self.state.energy_to_sell_dict[self.next_market.time_slot],
            "offered_sell_kWh": self.state.offered_sell_kWh[self.next_market.time_slot],
            "energy_to_buy": self.state.energy_to_buy_dict[self.next_market.time_slot],
            "offered_buy_kWh": self.state.offered_buy_kWh[self.next_market.time_slot],
            "free_storage": self.state.free_storage(self.next_market.time_slot),
            "used_storage": self.state.used_storage
        }

    def event_market_cycle(self):
        self._reject_all_pending_requests()
        self.register_on_market_cycle()
        if not self.should_use_default_strategy:
            self._reset_event_tick_counter()
            self.state.market_cycle(
                self.market_area.current_market.time_slot
                if self.market_area.current_market else None,
                self.next_market.time_slot,
                self.future_markets_time_slots
            )
            self.state.clamp_energy_to_sell_kWh([self.next_market.time_slot])
            self.state.clamp_energy_to_buy_kWh([self.next_market.time_slot])
            market_event_channel = f"{self.channel_prefix}/events/market"
            market_info = self.next_market.info
            if self.is_aggregator_controlled:
                market_info.update(default_market_info)
            market_info['device_info'] = self._device_info_dict
            market_info["event"] = "market"
            market_info['device_bill'] = self.device.stats.aggregated_stats["bills"] \
                if "bills" in self.device.stats.aggregated_stats else None
            market_info["area_uuid"] = self.device.uuid
            market_info["last_market_maker_rate"] = \
                get_current_market_maker_rate(self.area.current_market.time_slot) \
                if self.area.current_market else None
            market_info['last_market_stats'] = \
                self.market_area.stats.get_price_stats_current_market()
            self.redis.publish_json(market_event_channel, market_info)
            if self.is_aggregator_controlled:
                self.redis.aggregator.add_batch_market_event(self.device.uuid,
                                                             market_info,
                                                             self.area.global_objects)
            self._delete_past_state()
        else:
            super().event_market_cycle()

    def event_tick(self):
        if not self.connected and not self.is_aggregator_controlled:
            super().event_tick()
        else:
            self.state.tick(self.market_area, self.next_market.time_slot)
            self.state.clamp_energy_to_sell_kWh([self.next_market.time_slot])
            self.state.clamp_energy_to_buy_kWh([self.next_market.time_slot])

            while self.pending_requests:
                # We want to process requests as First-In-First-Out, so we use popleft
                req = self.pending_requests.popleft()
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
            self._dispatch_event_tick_to_external_agent()

    def _delete_offer_aggregator(self, arguments):
        if ("offer" in arguments and arguments["offer"] is not None) and \
                not self.offers.is_offer_posted(self.next_market.id, arguments["offer"]):
            raise Exception("Offer_id is not associated with any posted offer.")

        try:
            to_delete_offer_id = arguments["offer"] if "offer" in arguments else None
            deleted_offers = self.offers.remove_offer_from_cache_and_market(
                self.next_market, to_delete_offer_id)
            self.state.offered_sell_kWh[self.next_market.time_slot] = \
                self.offers.open_offer_energy(self.next_market.id)
            self.state.clamp_energy_to_sell_kWh([self.next_market.time_slot])
            return {
                "command": "offer_delete", "status": "ready",
                "deleted_offers": deleted_offers,
                "area_uuid": self.device.uuid,
                "transaction_id": arguments.get("transaction_id", None)
            }
        except Exception:
            return {
                "command": "offer_delete", "status": "error",
                "area_uuid": self.device.uuid,
                "error_message": f"Error when handling offer delete "
                                 f"on area {self.device.name} with arguments {arguments}.",
                "transaction_id": arguments.get("transaction_id", None)}

    def _list_offers_aggregator(self, arguments):
        try:
            filtered_offers = [{"id": v.id, "price": v.price, "energy": v.energy}
                               for _, v in self.next_market.get_offers().items()
                               if v.seller == self.device.name]
            return {
                "command": "list_offers", "status": "ready", "offer_list": filtered_offers,
                "area_uuid": self.device.uuid,
                "transaction_id": arguments.get("transaction_id", None)}
        except Exception:
            return {
                "command": "list_offers", "status": "error",
                "area_uuid": self.device.uuid,
                "error_message": f"Error when listing offers on area {self.device.name}.",
                "transaction_id": arguments.get("transaction_id", None)}

    def _update_offer_aggregator(self, arguments):
        assert set(arguments.keys()) == {'price', 'energy', 'transaction_id', 'type'}
        if arguments['price'] < 0.0:
            return {
                "command": "update_offer", "status": "error",
                "area_uuid": self.device.uuid,
                "error_message": "Update offer is only possible with positive price.",
                "transaction_id": arguments.get("transaction_id", None)}

        with self.lock:
            arguments['seller'] = self.device.name
            arguments['seller_origin'] = self.device.name
            offer_arguments = {k: v
                               for k, v in arguments.items()
                               if k not in ["transaction_id", "type"]}

            open_offers = self.offers.open
            if len(open_offers) == 0:
                return {
                    "command": "update_offer", "status": "error",
                    "area_uuid": self.device.uuid,
                    "error_message": "Update offer is only possible if the old offer exist",
                    "transaction_id": arguments.get("transaction_id", None)}

            for offer, iterated_market_id in open_offers.items():
                iterated_market = self.area.get_future_market_from_id(iterated_market_id)
                if iterated_market is None:
                    continue
                try:
                    iterated_market.delete_offer(offer.id)
                    offer_arguments['energy'] = offer.energy
                    offer_arguments['price'] = \
                        (offer_arguments['price'] / offer_arguments['energy']) * offer.energy
                    new_offer = iterated_market.offer(**offer_arguments)
                    self.offers.replace(offer, new_offer, iterated_market.id)
                    return {
                        "command": "update_offer",
                        "area_uuid": self.device.uuid,
                        "status": "ready",
                        "offer": offer.to_JSON_string(),
                        "transaction_id": arguments.get("transaction_id", None),
                    }
                except MarketException:
                    continue

    def _offer_aggregator(self, arguments):
        required_args = {'price', 'energy', 'type', 'transaction_id'}
        allowed_args = required_args.union({'replace_existing'})

        # Check that all required arguments have been provided
        assert all(arg in arguments.keys() for arg in required_args)
        # Check that every provided argument is allowed
        assert all(arg in allowed_args for arg in arguments.keys())

        with self.lock:
            arguments['seller'] = self.device.name
            arguments['seller_origin'] = self.device.name
            arguments['seller_origin_id'] = self.device.uuid
            arguments['seller_id'] = self.device.uuid
            try:
                offer_arguments = {
                    k: v for k, v in arguments.items() if k not in ['transaction_id', 'type']}
                assert self.can_offer_be_posted(self.next_market.time_slot, **offer_arguments)

                replace_existing = offer_arguments.pop('replace_existing', True)

                offer = self.post_offer(
                    self.next_market, replace_existing=replace_existing, **offer_arguments)

                self.state.offered_sell_kWh[self.next_market.time_slot] = \
                    self.offers.open_offer_energy(self.next_market.id)
                self.state.clamp_energy_to_sell_kWh([self.next_market.time_slot])

                return {
                    "command": "offer",
                    "area_uuid": self.device.uuid,
                    "status": "ready",
                    "offer": offer.to_JSON_string(replace_existing=replace_existing),
                    "transaction_id": arguments.get("transaction_id", None),
                }
            except Exception:
                return {
                    "command": "offer", "status": "error",
                    "area_uuid": self.device.uuid,
                    "error_message": f"Error when handling offer create "
                                     f"on area {self.device.name} with arguments {arguments}.",
                    "transaction_id": arguments.get("transaction_id", None)}

    def _update_bid_aggregator(self, arguments):
        assert set(arguments.keys()) == {'price', 'energy', 'type', 'transaction_id'}
        bid_rate = arguments["price"] / arguments["energy"]
        if bid_rate < 0.0:
            return {
                "command": "update_bid", "status": "error",
                "area_uuid": self.device.uuid,
                "error_message": "Updated bid needs to have a positive price.",
                "transaction_id": arguments.get("transaction_id", None)}
        with self.lock:
            existing_bids = list(self.get_posted_bids(self.next_market))
            existing_bid_energy = sum([bid.energy for bid in existing_bids])

            for bid in existing_bids:
                assert bid.buyer == self.owner.name
                if bid.id in self.next_market.bids.keys():
                    bid = self.next_market.bids[bid.id]
                self.next_market.delete_bid(bid.id)

                self.remove_bid_from_pending(self.next_market.id, bid.id)
            if len(existing_bids) > 0:
                updated_bid = self.post_bid(self.next_market, bid_rate * existing_bid_energy,
                                            existing_bid_energy, buyer_origin=self.device.name,
                                            buyer_origin_id=self.device.uuid)
                return {
                    "command": "update_bid", "status": "ready",
                    "bid": updated_bid.to_JSON_string(),
                    "area_uuid": self.device.uuid,
                    "transaction_id": arguments.get("transaction_id", None)}
            else:
                return {
                    "command": "update_bid", "status": "error",
                    "area_uuid": self.device.uuid,
                    "error_message": "Updated bid would only work if the old exist in market.",
                    "transaction_id": arguments.get("transaction_id", None)}

    def _bid_aggregator(self, arguments):
        required_args = {'price', 'energy', 'type', 'transaction_id'}
        allowed_args = required_args.union({'replace_existing'})

        try:
            # Check that all required arguments have been provided
            assert all(arg in arguments.keys() for arg in required_args)
            # Check that every provided argument is allowed
            assert all(arg in allowed_args for arg in arguments.keys())

            arguments['buyer_origin'] = self.device.name
            assert self.can_bid_be_posted(self.next_market.time_slot, **arguments)

            replace_existing = arguments.get('replace_existing', True)
            bid = self.post_bid(
                self.next_market,
                arguments["price"],
                arguments["energy"],
                replace_existing=replace_existing,
                buyer_origin=arguments["buyer_origin"],
                buyer_origin_id=arguments["buyer_origin_id"]
            )
            self.state.offered_buy_kWh[self.next_market.time_slot] = \
                self.posted_bid_energy(self.next_market.id)
            self.state.clamp_energy_to_buy_kWh([self.next_market.time_slot])
            return {
                "command": "bid", "status": "ready",
                "bid": bid.to_JSON_string(replace_existing=replace_existing),
                "area_uuid": self.device.uuid,
                "transaction_id": arguments.get("transaction_id", None)}
        except Exception:
            return {
                "command": "bid", "status": "error",
                "area_uuid": self.device.uuid,
                "error_message": f"Error when handling bid create "
                                 f"on area {self.device.name} with arguments {arguments}.",
                "transaction_id": arguments.get("transaction_id", None)}

    def _delete_bid_aggregator(self, arguments):
        if ("bid" in arguments and arguments["bid"] is not None) and \
                not self.is_bid_posted(self.next_market, arguments["bid"]):
            return {
                "command": "bid_delete", "status": "error",
                "error_message": "Bid_id is not associated with any posted bid.",
                "area_uuid": self.device.uuid,
                "transaction_id": arguments.get("transaction_id", None)}
        try:
            to_delete_bid_id = arguments["bid"] if "bid" in arguments else None
            deleted_bids = \
                self.remove_bid_from_pending(self.next_market.id, bid_id=to_delete_bid_id)
            self.state.offered_buy_kWh[self.next_market.time_slot] = \
                self.posted_bid_energy(self.next_market.id)
            self.state.clamp_energy_to_buy_kWh([self.next_market.time_slot])
            return {
                "command": "bid_delete", "status": "ready", "deleted_bids": deleted_bids,
                "area_uuid": self.device.uuid,
                "transaction_id": arguments.get("transaction_id", None)}
        except Exception:
            return {
                "command": "bid_delete", "status": "error",
                "area_uuid": self.device.uuid,
                "error_message": f"Error when handling bid delete "
                                 f"on area {self.device.name} with arguments {arguments}.",
                "transaction_id": arguments.get("transaction_id", None)}

    def _list_bids_aggregator(self, arguments):
        try:
            return {
                "command": "list_bids", "status": "ready",
                "bid_list": self.filtered_bids_next_market,
                "area_uuid": self.device.uuid,
                "transaction_id": arguments.get("transaction_id", None)}
        except Exception as e:
            logging.error(f"Error when handling list bids on area {self.device.name}: "
                          f"Exception: {str(e)}")
            return {
                "command": "list_bids", "status": "error",
                "area_uuid": self.device.uuid,
                "error_message": f"Error when listing bids on area {self.device.name}.",
                "transaction_id": arguments.get("transaction_id", None)}


class StorageExternalStrategy(StorageExternalMixin, StorageStrategy):
    pass
