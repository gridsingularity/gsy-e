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
from d3a.constants import FLOATING_POINT_TOLERANCE


from d3a.d3a_core.exceptions import MarketException, OfferNotFoundException


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

    def __repr__(self):
        return "<IAAEngine [{s.owner.name}] {s.name} {s.markets.source.time_slot:%H:%M}>".format(
            s=self
        )

    def _forward_offer(self, offer, offer_id):
        if offer.price == 0:
            self.owner.log.info("Offer is not forwarded because price=0")
            return

        forwarded_offer = self.markets.target.offer(
            offer.price,
            offer.energy,
            self.owner.name,
            offer.original_offer_price
        )
        offer_info = OfferInfo(offer, forwarded_offer)
        self.forwarded_offers[forwarded_offer.id] = offer_info
        self.forwarded_offers[offer_id] = offer_info
        self.owner.log.debug(f"Forwarding offer {offer} to {forwarded_offer}")
        return forwarded_offer

    def _delete_forwarded_offer_entries(self, offer):
        offer_info = self.forwarded_offers.pop(offer.id, None)
        if not offer_info:
            return
        self.forwarded_offers.pop(offer_info.target_offer.id, None)
        self.forwarded_offers.pop(offer_info.source_offer.id, None)

    def tick(self, *, area):
        # Store age of offer
        for offer in self.markets.source.sorted_offers:
            if offer.id not in self.offer_age:
                self.offer_age[offer.id] = area.current_tick

        # Use `list()` to avoid in place modification errors
        for offer_id, age in list(self.offer_age.items()):
            if offer_id in self.forwarded_offers:
                continue
            if area.current_tick - age < self.min_offer_age:
                continue
            offer = self.markets.source.offers.get(offer_id)
            if not offer:
                # Offer has gone - remove from age dict
                del self.offer_age[offer_id]
                continue
            if not self.owner.usable_offer(offer):
                # Forbidden offer (i.e. our counterpart's)
                continue

            # Should never reach this point.
            # This means that the IAA is forwarding offers with the same seller and buyer name.
            # If we ever again reach a situation like this, we should never forward the offer.
            if self.owner.name == offer.seller:
                continue

            forwarded_offer = self._forward_offer(offer, offer_id)
            if forwarded_offer:
                self.owner.log.info("Offering %s", forwarded_offer)

    def event_trade(self, *, trade):
        offer_info = self.forwarded_offers.get(trade.offer.id)
        if not offer_info:
            # Trade doesn't concern us
            return

        if trade.offer.id == offer_info.target_offer.id:
            # Offer was accepted in target market - buy in source
            residual_info = None
            source_rate = offer_info.source_offer.price / offer_info.source_offer.energy
            target_rate = offer_info.target_offer.price / offer_info.target_offer.energy
            assert abs(source_rate) <= abs(target_rate) + FLOATING_POINT_TOLERANCE, \
                f"offer: source_rate ({source_rate}) is not lower than target_rate ({target_rate})"

            if trade.offer.energy < offer_info.source_offer.energy:
                try:
                    residual_info = ResidualInfo(
                        forwarded=self.trade_residual.pop(trade.offer.id),
                        age=self.offer_age[offer_info.source_offer.id]
                    )
                except KeyError:
                    self.owner.log.error("Not forwarding residual offer for "
                                         "{} (Forwarded offer not found)".format(trade.offer))

            try:
                trade_offer_rate = trade.offer.price / trade.offer.energy
                trade_source = self.owner.accept_offer(
                    self.markets.source,
                    offer_info.source_offer,
                    energy=trade.offer.energy,
                    buyer=self.owner.name,
                    trade_rate=trade_offer_rate,
                    original_trade_rate=trade.original_trade_rate
                )

            except OfferNotFoundException:
                raise OfferNotFoundException()
            self.owner.log.info(
                f"[{self.markets.source.time_slot_str}] Offer accepted {trade_source}")

            if residual_info is not None:
                # connect residual of the forwarded offer to that of the source offer
                if trade_source.residual is not None:
                    if trade_source.residual.id not in self.forwarded_offers:
                        res_offer_info = OfferInfo(trade_source.residual, residual_info.forwarded)
                        self.forwarded_offers[trade_source.residual.id] = res_offer_info
                        self.forwarded_offers[residual_info.forwarded.id] = res_offer_info
                        self.offer_age[trade_source.residual.id] = residual_info.age
                        self.ignored_offers.add(trade_source.residual.id)
                else:
                    self.owner.log.error(
                        "Expected residual offer in source market trade {} - deleting "
                        "corresponding offer in target market".format(trade_source)
                    )
                    self.markets.target.delete_offer(residual_info.forwarded)

            self._delete_forwarded_offer_entries(offer_info.source_offer)
            self.offer_age.pop(offer_info.source_offer.id, None)

        elif trade.offer.id == offer_info.source_offer.id:
            # Offer was bought in source market by another party
            try:
                self.markets.target.delete_offer(offer_info.target_offer)
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
                self.markets.target.delete_offer(offer_info.target_offer)
                self._delete_forwarded_offer_entries(offer_info.source_offer)
            except MarketException:
                self.owner.log.exception("Error deleting InterAreaAgent offer")
        # TODO: Should potentially handle the flip side, by not deleting the source market offer
        # but by deleting the offered_offers entries

    def event_offer_changed(self, *, market_id, existing_offer, new_offer):
        market = self.owner._get_market_from_market_id(market_id)
        if market is None:
            return

        if market == self.markets.target and existing_offer.seller == self.owner.name:
            # one of our forwarded offers was split, so save the residual offer
            # for handling the upcoming trade event
            assert existing_offer.id not in self.trade_residual, \
                   "Offer should only change once before each trade."

            self.trade_residual[existing_offer.id] = new_offer

        elif market == self.markets.source and existing_offer.id in self.forwarded_offers:
            # an offer in the source market was split - delete the corresponding offer
            # in the target market and forward the new residual offer

            if not self.owner.usable_offer(existing_offer) or \
                    self.owner.name == existing_offer.seller:
                return

            if new_offer.id in self.ignored_offers:
                self.ignored_offers.remove(new_offer.id)
                return
            self.offer_age[new_offer.id] = self.offer_age.pop(existing_offer.id)
            offer_info = self.forwarded_offers[existing_offer.id]
            forwarded = self._forward_offer(new_offer, new_offer.id)
            if not forwarded:
                return

            self.owner.log.info("Offer %s changed to residual offer %s",
                                offer_info.target_offer,
                                forwarded)

            # Do not delete the forwarded offer entries for the case of residual offers
            if existing_offer.seller != new_offer.seller:
                self._delete_forwarded_offer_entries(offer_info.source_offer)


class BalancingEngine(IAAEngine):

    def _forward_offer(self, offer, offer_id):
        forwarded_balancing_offer = self.markets.target.balancing_offer(
            offer.price,
            offer.energy,
            self.owner.name,
            from_agent=True
        )
        offer_info = OfferInfo(offer, forwarded_balancing_offer)
        self.forwarded_offers[forwarded_balancing_offer.id] = offer_info
        self.forwarded_offers[offer_id] = offer_info
        self.owner.log.debug(f"Forwarding balancing offer {offer} to {forwarded_balancing_offer}")
        return forwarded_balancing_offer
