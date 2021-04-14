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
import logging
from typing import List, Dict

from d3a.d3a_core.exceptions import MarketException
from d3a.models.strategy.external_strategies import ExternalMixin
from d3a.models.strategy.storage import StorageStrategy


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

    @property
    def _device_info_dict(self):
        return {
            'energy_to_sell': self.state.energy_to_sell_dict[self.next_market.time_slot],
            'energy_active_in_bids': self.state.offered_sell_kWh[self.next_market.time_slot],
            'energy_to_buy': self.state.energy_to_buy_dict[self.next_market.time_slot],
            'energy_active_in_offers': self.state.offered_buy_kWh[self.next_market.time_slot],
            'free_storage': self.state.free_storage(self.next_market.time_slot),
            'used_storage': self.state.used_storage,
            'energy_traded': self.energy_traded(self.next_market.id),
            'total_cost': self.energy_traded_costs(self.next_market.id),
        }

    def event_market_cycle(self):
        self._reject_all_pending_requests()
        self.register_on_market_cycle()
        if self.should_use_default_strategy:
            super().event_market_cycle()
        else:
            self.state.market_cycle(
                self.market_area.current_market.time_slot
                if self.market_area.current_market else None,
                self.next_market.time_slot,
                self.future_markets_time_slots
            )
            self.state.clamp_energy_to_sell_kWh([self.next_market.time_slot])
            self.state.clamp_energy_to_buy_kWh([self.next_market.time_slot])
            self._delete_past_state()

    def event_tick(self):
        if not self.connected and not self.is_aggregator_controlled:
            super().event_tick()
        else:
            self.state.tick(self.market_area, self.next_market.time_slot)
            self.state.clamp_energy_to_sell_kWh([self.next_market.time_slot])
            self.state.clamp_energy_to_buy_kWh([self.next_market.time_slot])
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
                    offer_arguments["seller"] = offer.seller
                    offer_arguments["seller_origin"] = offer.seller_origin
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
                                            existing_bid_energy)
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

            assert self.can_bid_be_posted(self.next_market.time_slot, **arguments)

            replace_existing = arguments.get('replace_existing', True)
            bid = self.post_bid(
                self.next_market,
                arguments["price"],
                arguments["energy"],
                replace_existing=replace_existing)
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
