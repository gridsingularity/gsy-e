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
from collections import namedtuple
from typing import Dict, Set  # noqa
from copy import deepcopy
from d3a.constants import FLOATING_POINT_TOLERANCE
from d3a_interface.constants_limits import ConstSettings
from d3a.d3a_core.util import short_offer_bid_log_str
from d3a.d3a_core.exceptions import MarketException, OfferNotFoundException
from d3a.models.market.grid_fees.base_model import GridFees

OfferInfo = namedtuple('OfferInfo', ('source_offer', 'target_offer'))
Markets = namedtuple('Markets', ('source', 'target'))
ResidualInfo = namedtuple('ResidualInfo', ('forwarded', 'age'))


class IAAEngine:
    def __init__(self, name: str, market_1, market_2, min_offer_age: int,
                 owner: "InterAreaAgent"):
        self.name = name
        self.markets = Markets(market_1, market_2)
        self.min_offer_age = min_offer_age
        self.owner = owner

        self.offer_age = {}  # type: Dict[str, int]
        # Offer.id -> OfferInfo
        self.forwarded_offers = {}  # type: Dict[str, OfferInfo]
        self.trade_residual = {}  # type Dict[str, Offer]
        self.ignored_offers = set()  # type: Set[str]
        self._not_forwarded_offers = {
            offer_id for offer_id in self.markets.source.offers.keys()
            if offer_id not in self.forwarded_offers
        }

    def __repr__(self):
        return "<IAAEngine [{s.owner.name}] {s.name} {s.markets.source.time_slot:%H:%M}>".format(
            s=self
        )

    def _offer_in_market(self, offer):

        kwargs = {
            "price": GridFees.update_forwarded_offer_with_fee(
                        offer.price, offer.original_offer_price,
                        self.markets.target.transfer_fee_ratio),
            "energy": offer.energy,
            "seller": self.owner.name,
            "original_offer_price": offer.original_offer_price,
            "dispatch_event": False,
            "seller_origin": offer.seller_origin,
            "adapt_price_with_fees": self.markets.target.transfer_fee_ratio > 0.0
        }

        if ConstSettings.GeneralSettings.EVENT_DISPATCHING_VIA_REDIS:
            return self.owner.offer(market_id=self.markets.target, offer_args=kwargs)
        else:

            return self.markets.target.offer(**kwargs)

    def _forward_offer(self, offer):
        # TODO: This is an ugly solution. After the december release this check needs to
        #  implemented after grid fee being incorporated while forwarding in target market
        if offer.price < 0.0:
            self.owner.log.debug("Offer is not forwarded because price < 0")
            return
        forwarded_offer = self._offer_in_market(offer)

        self._add_to_forward_offers(offer, forwarded_offer)
        self.owner.log.trace(f"Forwarding offer {offer} to {forwarded_offer}")
        # TODO: Ugly solution, required in order to decouple offer placement from
        # new offer event triggering
        self.markets.target.dispatch_market_offer_event(offer)
        return forwarded_offer

    def _delete_forwarded_offer_entries(self, offer):
        offer_info = self.forwarded_offers.pop(offer.id, None)
        if not offer_info:
            return
        self.forwarded_offers.pop(offer_info.target_offer.id, None)
        self.forwarded_offers.pop(offer_info.source_offer.id, None)

    def tick(self, *, area):
        self.propagate_offer(area.current_tick)

    def event_offer(self, market_id, offer):
        if market_id != self.markets.source.id:
            return
        if offer.id in self.forwarded_offers:
            return
        if offer.id in self.offer_age:
            return
        if offer.id not in self.markets.source.offers:
            # TODO: Potential further optimisation here
            # This case handles trade events that we receive but are not contained in any of
            # the source and target market. This happens when another device accepts the offer
            # before the offer event is dispatched to this market. Current solution is to
            # recalculate the _not_forwarded_offers dict. However, this could be fairly optimized
            # if the trade event was captured and notified that the offer was deleted/made partial
            self.repopulate_non_forwarded_offers()
        else:
            self._not_forwarded_offers.add(offer.id)
            self.offer_age[offer.id] = self.owner.owner.current_tick

    def repopulate_non_forwarded_offers(self):
        self._not_forwarded_offers.update({
            offer_id for offer_id in self.markets.source.offers.keys()
            if offer_id not in self.forwarded_offers
        })
        for offer_id in self._not_forwarded_offers:
            if offer_id not in self.offer_age:
                self.offer_age[offer_id] = self.owner.owner.current_tick

    def propagate_offer(self, current_tick):
        # Store age of offer
        for offer_id in self._not_forwarded_offers:
            if offer_id not in self.offer_age:
                self.offer_age[offer_id] = current_tick

        self._not_forwarded_offers.clear()
        # Use `list()` to avoid in place modification errors
        for offer_id, age in list(self.offer_age.items()):
            if offer_id in self.forwarded_offers:
                continue
            if current_tick - age < self.min_offer_age:
                continue
            offer = self.markets.source.offers.get(offer_id)
            if not offer:
                # Offer has gone - remove from age dict
                # Because an offer forwarding might trigger a trade event, the offer_age dict might
                # be modified, thus causing a removal from the offer_age dict. In such a case, even
                # if the offer is no longer in the offer_age dict, the execution should continue
                # normally.
                self.offer_age.pop(offer_id, None)
                continue
            if not self.owner.usable_offer(offer):
                # Forbidden offer (i.e. our counterpart's)
                self.offer_age.pop(offer_id, None)
                continue

            # Should never reach this point.
            # This means that the IAA is forwarding offers with the same seller and buyer name.
            # If we ever again reach a situation like this, we should never forward the offer.
            if self.owner.name == offer.seller:
                self.offer_age.pop(offer_id, None)
                continue

            forwarded_offer = self._forward_offer(offer)
            if forwarded_offer:
                self.owner.log.debug(f"Forwarded offer to {self.markets.source.name} "
                                     f"{self.owner.name}, {self.name} {forwarded_offer}")

    def event_trade(self, *, trade):
        offer_info = self.forwarded_offers.get(trade.offer.id)
        if not offer_info:
            # Trade doesn't concern us
            return

        if trade.offer.id == offer_info.target_offer.id:
            # Offer was accepted in target market - buy in source
            source_rate = offer_info.source_offer.price / offer_info.source_offer.energy
            target_rate = offer_info.target_offer.price / offer_info.target_offer.energy
            assert abs(source_rate) <= abs(target_rate) + FLOATING_POINT_TOLERANCE, \
                f"offer: source_rate ({source_rate}) is not lower than target_rate ({target_rate})"

            try:
                trade_offer_rate = trade.offer.price / trade.offer.energy
                updated_trade_bid_info = GridFees.update_forwarded_offer_trade_original_info(
                    trade.offer_bid_trade_info, offer_info.source_offer)
                trade_source = self.owner.accept_offer(
                    market_or_id=self.markets.source,
                    offer=offer_info.source_offer,
                    energy=trade.offer.energy,
                    buyer=self.owner.name,
                    trade_rate=trade_offer_rate,
                    trade_bid_info=updated_trade_bid_info,
                    buyer_origin=trade.buyer_origin
                )

            except OfferNotFoundException:
                raise OfferNotFoundException()
            self.owner.log.debug(
                f"[{self.markets.source.time_slot_str}] Offer accepted {trade_source}")

            self._delete_forwarded_offer_entries(offer_info.source_offer)
            self.offer_age.pop(offer_info.source_offer.id, None)

        elif trade.offer.id == offer_info.source_offer.id:
            # Offer was bought in source market by another party
            try:
                self.owner.delete_offer(self.markets.target, offer_info.target_offer)
            except OfferNotFoundException:
                pass
            except MarketException as ex:
                self.owner.log.error("Error deleting InterAreaAgent offer: {}".format(ex))

            self._delete_forwarded_offer_entries(offer_info.source_offer)
            self.offer_age.pop(offer_info.source_offer.id, None)
        else:
            raise RuntimeError("Unknown state. Can't happen")

        assert offer_info.source_offer.id not in self.forwarded_offers
        assert offer_info.target_offer.id not in self.forwarded_offers

    def event_offer_deleted(self, *, offer):
        if offer.id in self.offer_age:
            # Offer we're watching in source market was deleted - remove
            del self.offer_age[offer.id]

        offer_info = self.forwarded_offers.get(offer.id)
        if not offer_info:
            # Deletion doesn't concern us
            return

        if offer_info.source_offer.id == offer.id:
            # Offer in source market of an offer we're already offering in the target market
            # was deleted - also delete in target market
            try:
                self.owner.delete_offer(self.markets.target, offer_info.target_offer)
                self._delete_forwarded_offer_entries(offer_info.source_offer)
            except MarketException:
                self.owner.log.exception("Error deleting InterAreaAgent offer")
        # TODO: Should potentially handle the flip side, by not deleting the source market offer
        # but by deleting the offered_offers entries

    def event_offer_split(self, *, market_id, original_offer, accepted_offer, residual_offer):
        market = self.owner._get_market_from_market_id(market_id)
        if market is None:
            return

        if market == self.markets.target and accepted_offer.id in self.forwarded_offers:
            # offer was split in target market, also split in source market

            local_offer = self.forwarded_offers[original_offer.id].source_offer
            original_offer_price = local_offer.original_offer_price \
                if local_offer.original_offer_price is not None else local_offer.price

            local_split_offer, local_residual_offer = \
                self.markets.source.split_offer(local_offer, accepted_offer.energy,
                                                original_offer_price)

            #  add the new offers to forwarded_offers
            self._add_to_forward_offers(local_residual_offer, residual_offer)
            self._add_to_forward_offers(local_split_offer, accepted_offer)

        elif market == self.markets.source and accepted_offer.id in self.forwarded_offers:
            # offer was split in source market, also split in target market
            if not self.owner.usable_offer(accepted_offer) or \
                    self.owner.name == accepted_offer.seller:
                return

            local_offer = self.forwarded_offers[original_offer.id].source_offer

            original_offer_price = local_offer.original_offer_price \
                if local_offer.original_offer_price is not None else local_offer.price

            local_split_offer, local_residual_offer = \
                self.markets.target.split_offer(local_offer, accepted_offer.energy,
                                                original_offer_price)

            #  add the new offers to forwarded_offers
            self._add_to_forward_offers(residual_offer, local_residual_offer)
            self._add_to_forward_offers(accepted_offer, local_split_offer)
        else:
            return

        if original_offer.id in self.offer_age:
            self.offer_age[residual_offer.id] = self.offer_age.pop(original_offer.id)

        self.owner.log.debug(f"Offer {short_offer_bid_log_str(local_offer)} was split into "
                             f"{short_offer_bid_log_str(local_split_offer)} and "
                             f"{short_offer_bid_log_str(local_residual_offer)}")

    def _add_to_forward_offers(self, source_offer, target_offer):
        offer_info = OfferInfo(deepcopy(source_offer), deepcopy(target_offer))
        self.forwarded_offers[source_offer.id] = offer_info
        self.forwarded_offers[target_offer.id] = offer_info


class BalancingEngine(IAAEngine):

    def _forward_offer(self, offer):
        forwarded_balancing_offer = self.markets.target.balancing_offer(
            offer.price,
            offer.energy,
            self.owner.name,
            from_agent=True
        )
        self._add_to_forward_offers(offer, forwarded_balancing_offer)
        self.owner.log.trace(f"Forwarding balancing offer {offer} to {forwarded_balancing_offer}")
        return forwarded_balancing_offer
