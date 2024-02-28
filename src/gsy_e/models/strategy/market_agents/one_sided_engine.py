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
from collections import namedtuple
from typing import Dict, Optional  # noqa

from gsy_framework.constants_limits import ConstSettings
from gsy_framework.data_classes import Offer, TraderDetails, TradeBidOfferInfo
from gsy_framework.enums import SpotMarketTypeEnum
from gsy_framework.utils import limit_float_precision

from gsy_e.constants import FLOATING_POINT_TOLERANCE
from gsy_e.gsy_e_core.exceptions import MarketException, OfferNotFoundException
from gsy_e.gsy_e_core.util import short_offer_bid_log_str

OfferInfo = namedtuple("OfferInfo", ("source_offer", "target_offer"))
Markets = namedtuple("Markets", ("source", "target"))
ResidualInfo = namedtuple("ResidualInfo", ("forwarded", "age"))


class MAEngine:
    """Handle forwarding offers to the connected one-sided market."""
    # pylint: disable=too-many-arguments,too-many-instance-attributes

    def __init__(self, name: str, market_1, market_2, min_offer_age: int, owner):
        self.name = name
        self.markets = Markets(market_1, market_2)
        self.min_offer_age = min_offer_age
        self.owner = owner

        self.offer_age: Dict[str, int] = {}
        # Offer.id -> OfferInfo
        self.forwarded_offers: Dict[str, OfferInfo] = {}
        self.trade_residual: Dict[str, Offer] = {}
        self._current_tick = 0

    def __repr__(self):
        return "<MAEngine [{s.owner.name}] {s.name} {s.markets.source.time_slot:%H:%M}>".format(
            s=self
        )

    def _update_offer_requirements_prices(self, offer):
        requirements = []
        for requirement in offer.requirements or []:
            updated_requirement = {**requirement}
            if "price" in updated_requirement:
                energy = updated_requirement.get("energy") or offer.energy
                original_offer_price = updated_requirement["price"] + offer.accumulated_grid_fees
                updated_price = self.markets.target.fee_class.update_forwarded_offer_with_fee(
                    updated_requirement["price"] / energy,
                    original_offer_price / energy) * energy
                updated_requirement["price"] = updated_price
            requirements.append(updated_requirement)
        return requirements

    def _offer_in_market(self, offer):
        updated_price = limit_float_precision(
            self.markets.target.fee_class.update_forwarded_offer_with_fee(
                offer.energy_rate, offer.original_energy_rate) * offer.energy)

        kwargs = {
            "price": updated_price,
            "energy": offer.energy,
            "seller": TraderDetails(
                self.owner.name, self.owner.uuid,
                offer.seller.origin, offer.seller.origin_uuid
            ),
            "original_price": offer.original_price,
            "dispatch_event": False,
            "time_slot": offer.time_slot
        }

        return self.owner.post_offer(market=self.markets.target, replace_existing=False, **kwargs)

    def _forward_offer(self, offer: Offer) -> Optional[Offer]:
        # pylint: disable=fixme
        # TODO: This is an ugly solution. After the december release this check needs to
        #  implemented after grid fee being incorporated while forwarding in target market
        if offer.price < -FLOATING_POINT_TOLERANCE:
            self.owner.log.debug("Offer is not forwarded because price < 0")
            return None
        try:
            forwarded_offer = self._offer_in_market(offer)
        except MarketException:
            self.owner.log.debug("Offer is not forwarded because grid fees of the target market "
                                 "lead to a negative offer price.")
            return None

        self._add_to_forward_offers(offer, forwarded_offer)
        self.owner.log.trace(f"Forwarding offer {offer} to {forwarded_offer}")
        # TODO: Ugly solution, required in order to decouple offer placement from
        # new offer event triggering
        self.markets.target.dispatch_market_offer_event(forwarded_offer)
        return forwarded_offer

    def _delete_forwarded_offer_entries(self, offer):
        offer_info = self.forwarded_offers.pop(offer.id, None)
        if not offer_info:
            return
        self.forwarded_offers.pop(offer_info.target_offer.id, None)
        self.forwarded_offers.pop(offer_info.source_offer.id, None)
        self.offer_age.pop(offer_info.target_offer.id, None)
        self.offer_age.pop(offer_info.source_offer.id, None)

    def tick(self, *, area):
        """Perform actions that need to be done when TICK event is triggered."""
        self._current_tick = area.current_tick

        self._propagate_offer(area.current_tick)

    def _propagate_offer(self, current_tick):
        # Store age of offer
        for offer in self.markets.source.offers.values():
            if offer.id not in self.offer_age:
                self.offer_age[offer.id] = current_tick

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
            # This means that the MA is forwarding offers with the same seller and buyer name.
            # If we ever again reach a situation like this, we should never forward the offer.
            if self.owner.name == offer.seller.name:
                self.offer_age.pop(offer_id, None)
                continue

            forwarded_offer = self._forward_offer(offer)
            if forwarded_offer:
                self.owner.log.debug(f"Forwarded offer to {self.markets.source.name} "
                                     f"{self.owner.name}, {self.name} {forwarded_offer}")

    def event_offer_traded(self, *, trade):
        """Perform actions that need to be done when OFFER_TRADED event is triggered."""
        offer_info = self.forwarded_offers.get(trade.match_details["offer"].id)
        if not offer_info:
            # Trade doesn't concern us
            return

        if trade.match_details["offer"].id == offer_info.target_offer.id:
            # Offer was accepted in target market - buy in source
            source_rate = offer_info.source_offer.energy_rate
            target_rate = offer_info.target_offer.energy_rate
            assert abs(source_rate) <= abs(target_rate) + 0.0001, \
                f"offer: source_rate ({source_rate}) is not lower than target_rate ({target_rate})"

            updated_trade_bid_info = \
                self.markets.source.fee_class.update_forwarded_offer_trade_original_info(
                    trade.offer_bid_trade_info, offer_info.source_offer)
            try:
                if ConstSettings.MASettings.MARKET_TYPE == SpotMarketTypeEnum.ONE_SIDED.value:
                    # One sided market should subtract the fees
                    trade_offer_rate = trade.trade_rate - \
                                       trade.fee_price / trade.traded_energy
                    if not updated_trade_bid_info:
                        updated_trade_bid_info = TradeBidOfferInfo(
                            None, None, (
                                offer_info.source_offer.original_price /
                                offer_info.source_offer.energy), source_rate, 0.)
                    updated_trade_bid_info.trade_rate = trade_offer_rate

                trade_source = self.owner.accept_offer(
                    market=self.markets.source,
                    offer=offer_info.source_offer,
                    energy=trade.traded_energy,
                    buyer=TraderDetails(
                        self.owner.name, self.owner.uuid,
                        trade.buyer.origin, trade.buyer.origin_uuid),
                    trade_bid_info=updated_trade_bid_info,
                )

            except OfferNotFoundException as ex:
                raise OfferNotFoundException() from ex
            self.owner.log.debug(
                f"[{self.markets.source.time_slot_str}] Offer accepted {trade_source}")

            self._delete_forwarded_offer_entries(offer_info.source_offer)
            self.offer_age.pop(offer_info.source_offer.id, None)

        elif trade.match_details["offer"].id == offer_info.source_offer.id:
            # Offer was bought in source market by another party
            try:
                self.owner.delete_offer(self.markets.target, offer_info.target_offer)
            except OfferNotFoundException:
                pass
            except MarketException:
                self.owner.log.exception("Error deleting MarketAgent offer:")

            self._delete_forwarded_offer_entries(offer_info.source_offer)
            self.offer_age.pop(offer_info.source_offer.id, None)

            # Forward the residual offer since the original offer was also forwarded
            if trade.residual:
                self._forward_offer(trade.residual)
        else:
            raise RuntimeError("Unknown state. Can't happen")

        assert offer_info.source_offer.id not in self.forwarded_offers
        assert offer_info.target_offer.id not in self.forwarded_offers

    def event_offer_deleted(self, *, offer):
        """Perform actions that need to be done when OFFER_DELETED event is triggered."""
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
            except MarketException:
                self.owner.log.exception("Error deleting MarketAgent offer")
        self._delete_forwarded_offer_entries(offer_info.source_offer)

    def event_offer_split(self, *, market_id, original_offer, accepted_offer, residual_offer):
        """Perform actions that need to be done when OFFER_SPLIT event is triggered."""
        market = self.owner.get_market_from_market_id(market_id)
        if market is None:
            return

        if market == self.markets.target and accepted_offer.id in self.forwarded_offers:
            # offer was split in target market, also split in source market

            local_offer = self.forwarded_offers[original_offer.id].source_offer
            original_price = local_offer.original_price \
                if local_offer.original_price is not None else local_offer.price

            local_split_offer, local_residual_offer = \
                self.markets.source.split_offer(local_offer, accepted_offer.energy,
                                                original_price)

            #  add the new offers to forwarded_offers
            self._add_to_forward_offers(local_residual_offer, residual_offer)
            self._add_to_forward_offers(local_split_offer, accepted_offer)

        elif market == self.markets.source and accepted_offer.id in self.forwarded_offers:
            # offer was split in source market, also split in target market
            if not self.owner.usable_offer(accepted_offer) or \
                    self.owner.name == accepted_offer.seller.name:
                return

            local_offer = self.forwarded_offers[original_offer.id].source_offer

            original_price = local_offer.original_price \
                if local_offer.original_price is not None else local_offer.price

            local_split_offer, local_residual_offer = \
                self.markets.target.split_offer(local_offer, accepted_offer.energy,
                                                original_price)

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
        offer_info = OfferInfo(Offer.copy(source_offer), Offer.copy(target_offer))
        self.forwarded_offers[source_offer.id] = offer_info
        self.forwarded_offers[target_offer.id] = offer_info

    def event_offer(self, offer: Offer) -> None:
        """Perform actions on the event of the creation of a new offer."""
        if (ConstSettings.MASettings.MARKET_TYPE == SpotMarketTypeEnum.TWO_SIDED.value and
                self.min_offer_age == 0):
            # Propagate offer immediately if the MIN_OFFER_AGE is set to zero.
            if offer.id not in self.offer_age:
                self.offer_age[offer.id] = self._current_tick

            if offer.id in self.forwarded_offers:
                return

            offer_age = self.offer_age[offer.id]
            if self._current_tick - offer_age < self.min_offer_age:
                return
            offer = self.markets.source.offers.get(offer.id)
            if not offer:
                return
            if not self.owner.usable_offer(offer):
                self.offer_age.pop(offer.id, None)
                return

            if self.owner.name == offer.seller.name:
                self.offer_age.pop(offer.id, None)
                return

            forwarded_offer = self._forward_offer(offer)
            if forwarded_offer:
                self.owner.log.debug(f"Forwarded offer to {self.markets.source.name} "
                                     f"{self.owner.name}, {self.name} {forwarded_offer}")


class BalancingEngine(MAEngine):
    """Handle forwarding offers to the connected balancing market."""

    def _forward_offer(self, offer):
        forwarded_balancing_offer = self.markets.target.balancing_offer(
            offer.price, offer.energy,
            TraderDetails(
                self.owner.name, self.owner.uuid, offer.seller.origin, offer.seller.origin_uuid),
            from_agent=True
        )
        self._add_to_forward_offers(offer, forwarded_balancing_offer)
        self.owner.log.trace(f"Forwarding balancing offer {offer} to {forwarded_balancing_offer}")
        return forwarded_balancing_offer
