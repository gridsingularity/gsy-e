from collections import namedtuple
from typing import Dict, Set  # noqa

from d3a.exceptions import MarketException, OfferNotFoundException, BidNotFound
from d3a.models.strategy.base import BaseStrategy, _TradeLookerUpper
from d3a.models.strategy.const import ConstSettings
from d3a.util import make_iaa_name


OfferInfo = namedtuple('OfferInfo', ('source_offer', 'target_offer'))
BidInfo = namedtuple('BidInfo', ('source_bid', 'target_bid'))
Markets = namedtuple('Markets', ('source', 'target'))
ResidualInfo = namedtuple('ResidualInfo', ('forwarded', 'age'))


class IAAEngine:
    def __init__(self, name: str, market_1, market_2, min_offer_age: int, transfer_fee_pct: int,
                 owner: "InterAreaAgent"):
        self.name = name
        self.markets = Markets(market_1, market_2)
        self.min_offer_age = min_offer_age
        self.transfer_fee_pct = transfer_fee_pct
        self.owner = owner

        self.offer_age = {}  # type: Dict[str, int]
        # Offer.id -> OfferInfo
        self.offered_offers = {}  # type: Dict[str, OfferInfo]
        self.trade_residual = {}  # type Dict[str, Offer]
        self.ignored_offers = set()  # type: Set[str]

        self.offered_bids = {}  # type: Dict[str, BidInfo]

    def __repr__(self):
        return "<IAAEngine [{s.owner.name}] {s.name} {s.markets.source.time_slot:%H:%M}>".format(
            s=self
        )

    def _forward_offer(self, offer, offer_id):
        forwarded_offer = self.markets.target.offer(
            offer.price + (offer.price * (self.transfer_fee_pct / 100)),
            offer.energy,
            self.owner.name
        )
        offer_info = OfferInfo(offer, forwarded_offer)
        self.offered_offers[forwarded_offer.id] = offer_info
        self.offered_offers[offer_id] = offer_info
        return forwarded_offer

    def _forward_bid(self, bid):
        if bid.buyer == self.markets.target.area.name and \
                bid.seller == self.markets.source.area.name:
            return
        forwarded_bid = self.markets.target.bid(bid.price, bid.energy,
                                                self.markets.source.area.name,
                                                self.markets.target.area.name)
        bid_coupling = BidInfo(bid, forwarded_bid)
        self.offered_bids[forwarded_bid.id] = bid_coupling
        self.offered_bids[bid.id] = bid_coupling
        return forwarded_bid

    def _match_offers_bids(self):
        # Pay as bid first
        # There are 2 simplistic approaches to the problem
        # 1. Match the cheapest offer with the most expensive bid. This will favor the sellers
        # 2. Match the cheapest offer with the cheapest bid. This will favor the buyers,
        #    since the most affordable offers will be allocated for the most aggressive buyers.

        def get_list_from_offered_dict(offered, source):
            return list(
                map(lambda x: getattr(x, source),
                    list(offered.values())
                    )
            )

        # Sorted bids in descending order
        sorted_bids = list(reversed(sorted(
            get_list_from_offered_dict(self.offered_bids, "source_bid"),
            key=lambda b: b.price / b.energy))
        )
        # Sorted offers in ascending order
        sorted_offers = list((sorted(
            get_list_from_offered_dict(self.offered_offers, "source_offer"),
            key=lambda o: o.price / o.energy))
        )
        for offer in sorted_offers:
            for bid in sorted_bids:
                if bid.id in self.offered_bids and offer.id in self.offered_offers and \
                        offer.price / offer.energy <= bid.price / bid.energy:
                    selected_energy = bid.energy if bid.energy < offer.energy else offer.energy
                    if self.offered_bids[bid.id].target_bid.id == bid.id:
                        continue

                    self.markets.source.accept_offer(offer,
                                                     buyer=self.owner.name,
                                                     energy=selected_energy)
                    deleted_offerinfo = self.offered_offers.pop(offer.id)
                    self.offered_offers.pop(deleted_offerinfo.target_offer.id)

                    self.markets.source.accept_bid(bid, selected_energy, seller=self.owner.name)
                    bid_to_remove = bid
                    bid_info = self.offered_bids.pop(bid_to_remove.id, None)
                    if not bid_info:
                        continue
                    if bid_info.target_bid.id in self.offered_bids:
                        self.markets.target.delete_bid(bid_info.target_bid.id)
                        self.offered_bids.pop(bid_info.target_bid.id, None)
                    if bid_info.source_bid.id in self.offered_bids:
                        self.markets.source.delete_bid(bid_info.source_bid.id)
                        self.offered_bids.pop(bid_info.source_bid.id, None)

    def tick(self, *, area):
        # Store age of offer
        for offer in self.markets.source.sorted_offers:
            if offer.id not in self.offer_age:
                self.offer_age[offer.id] = area.current_tick

        # Use `list()` to avoid in place modification errors
        for offer_id, age in list(self.offer_age.items()):
            if offer_id in self.offered_offers:
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
            self.owner.log.info("Offering %s", forwarded_offer)

        if ConstSettings.INTER_AREA_AGENT_MARKET_TYPE == 2:
            self._match_offers_bids()

            for bid_id, bid in self.markets.source.bids.items():
                if bid_id not in self.offered_bids:
                    self._forward_bid(bid)

    def event_bid_traded(self, *, traded_bid):
        bid_info = self.offered_bids.get(traded_bid.offer.id)
        if not bid_info:
            return

        # Bid was traded in target market, buy in source
        if traded_bid.offer.id == bid_info.target_bid.id:
            self.markets.source.accept_bid(
                bid_info.source_bid,
                energy=traded_bid.offer.energy,
                seller=self.owner.name
            )

            current_bid_info = self.offered_bids.pop(bid_info.source_bid.id, None)
            if current_bid_info is not None:
                self.offered_bids.pop(current_bid_info.target_bid.id, None)
            self.offered_bids.pop(bid_info.target_bid.id, None)

        # Bid was traded in the source market by someone else
        elif traded_bid.offer.id == bid_info.source_bid.id:
            # Delete target bid
            try:
                self.markets.target.delete_bid(bid_info.target_bid)
            except BidNotFound:
                pass
            self.offered_bids.pop(bid_info.source_bid.id, None)
            self.offered_bids.pop(bid_info.target_bid.id, None)
        else:
            raise Exception(f"Invalid bid state for IAA {self.owner.name}: "
                            f"traded bid {traded_bid} was not in offered bids tuple {bid_info}")

    def event_trade(self, *, trade):
        offer_info = self.offered_offers.get(trade.offer.id)
        if not offer_info:
            # Trade doesn't concern us
            return

        if trade.offer.id == offer_info.target_offer.id:
            # Offer was accepted in target market - buy in source
            residual_info = None
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
                trade_source = self.owner.accept_offer(
                    self.markets.source,
                    offer_info.source_offer,
                    energy=trade.offer.energy,
                    buyer=self.owner.name
                )
            except OfferNotFoundException:
                raise OfferNotFoundException()
            self.owner.log.info("Offer accepted %s", trade_source)

            if residual_info is not None:
                # connect residual of the forwarded offer to that of the source offer
                if trade_source.residual is not None:
                    if trade_source.residual.id not in self.offered_offers:
                        res_offer_info = OfferInfo(trade_source.residual, residual_info.forwarded)
                        self.offered_offers[trade_source.residual.id] = res_offer_info
                        self.offered_offers[residual_info.forwarded.id] = res_offer_info
                        self.offer_age[trade_source.residual.id] = residual_info.age
                        self.ignored_offers.add(trade_source.residual.id)
                else:
                    self.owner.log.error(
                        "Expected residual offer in source market trade {} - deleting "
                        "corresponding offer in target market".format(trade_source)
                    )
                    self.markets.target.delete_offer(residual_info.forwarded)

            current_offer_info = self.offered_offers.pop(offer_info.source_offer.id, None)
            if current_offer_info is not None:
                self.offered_offers.pop(current_offer_info.target_offer.id, None)
            self.offered_offers.pop(offer_info.target_offer.id, None)
            self.offered_offers.pop(trade.offer.id, None)
            self.offer_age.pop(offer_info.source_offer.id, None)

        elif trade.offer.id == offer_info.source_offer.id and trade.buyer == self.owner.name:
            # Flip side of the event from above buying action - do nothing
            pass
        elif trade.offer.id == offer_info.source_offer.id:
            # Offer was bought in source market by another party
            try:
                self.markets.target.delete_offer(offer_info.target_offer)
            except OfferNotFoundException:
                pass
            except MarketException as ex:
                self.owner.log.error("Error deleting InterAreaAgent offer: {}".format(ex))
            self.offered_offers.pop(offer_info.source_offer.id, None)
            self.offered_offers.pop(offer_info.target_offer.id, None)
            self.offer_age.pop(offer_info.source_offer.id, None)
        else:
            raise RuntimeError("Unknown state. Can't happen")

    def event_bid_deleted(self, *, bid):
        from d3a.models.market import Bid
        bid_id = bid.id if isinstance(bid, Bid) else bid
        bid_info = self.offered_bids.get(bid_id)

        if not bid_info:
            # Deletion doesn't concern us
            return

        self.offered_bids.pop(bid_id)
        if bid_info.source_bid.id == bid_id:
            # Offer in source market of an offer we're already offering in the target market
            # was deleted - also delete in target market
            try:
                self.markets.target.delete_bid(bid_info.target_bid.id)
                self.offered_bids.pop(bid_info.target_bid.id, None)
            except MarketException:
                self.owner.log.exception("Error deleting InterAreaAgent offer")

    def event_offer_deleted(self, *, offer):
        if offer.id in self.offer_age:
            # Offer we're watching in source market was deleted - remove
            del self.offer_age[offer.id]

        offer_info = self.offered_offers.get(offer.id)
        if not offer_info:
            # Deletion doesn't concern us
            return

        if offer_info.source_offer.id == offer.id:
            # Offer in source market of an offer we're already offering in the target market
            # was deleted - also delete in target market
            try:
                self.markets.target.delete_offer(offer_info.target_offer)
            except MarketException:
                self.owner.log.exception("Error deleting InterAreaAgent offer")

    def event_offer_changed(self, *, market, existing_offer, new_offer):
        if market == self.markets.target and existing_offer.seller == self.owner.name:
            # one of our forwarded offers was split, so save the residual offer
            # for handling the upcoming trade event
            assert existing_offer.id not in self.trade_residual, \
                   "Offer should only change once before each trade."
            self.trade_residual[existing_offer.id] = new_offer

        elif market == self.markets.source and existing_offer.id in self.offered_offers:
            # an offer in the source market was split - delete the corresponding offer
            # in the target market and forward the new residual offer
            if new_offer.id in self.ignored_offers:
                self.ignored_offers.remove(new_offer.id)
                return
            self.offer_age[new_offer.id] = self.offer_age.pop(existing_offer.id)
            offer_info = self.offered_offers[existing_offer.id]
            forwarded = self._forward_offer(new_offer, new_offer.id)

            self.owner.log.info("Offer %s changed to residual offer %s",
                                offer_info.target_offer,
                                forwarded)
            # Do not delete the offered offer entries for the case of residual offers
            if existing_offer.seller != new_offer.seller:
                del self.offered_offers[offer_info.target_offer.id]
                del self.offered_offers[offer_info.source_offer.id]


class InterAreaAgent(BaseStrategy):
    parameters = ('owner', 'higher_market', 'lower_market', 'transfer_fee_pct',
                  'min_offer_age', 'tick_ratio')

    def __init__(self, *, owner, higher_market, lower_market, transfer_fee_pct=1, min_offer_age=1,
                 tick_ratio=2):
        """
        Equalize markets

        :param higher_market:
        :type higher_market: Market
        :param lower_market:
        :type lower_market: Market
        :param min_offer_age: Minimum age of offer before transferring
        :param tick_ratio: How often markets should be compared (default 4 := 1/4)
        """
        super().__init__()
        self.owner = owner
        self.name = make_iaa_name(owner)

        self.engines = [
            IAAEngine('High -> Low', higher_market, lower_market, min_offer_age, transfer_fee_pct,
                      self),
            IAAEngine('Low -> High', lower_market, higher_market, min_offer_age, transfer_fee_pct,
                      self),
        ]

        self.time_slot = higher_market.time_slot.strftime("%H:%M")
        self.tick_ratio = tick_ratio

        # serialization parameters
        self.higher_market = higher_market
        self.lower_market = lower_market
        self.transfer_fee_pct = transfer_fee_pct
        self.min_offer_age = min_offer_age

    @property
    def trades(self):
        return _TradeLookerUpper(self.name)

    def __repr__(self):
        return "<InterAreaAgent {s.name} {s.time_slot}>".format(s=self)

    def usable_offer(self, offer):
        """Prevent IAAEngines from trading their counterpart's offers"""
        return all(offer.id not in engine.offered_offers.keys() for engine in self.engines)

    def usable_bid(self, bid):
        """Prevent IAAEngines from trading their counterpart's bids"""
        return all(bid.id not in engine.offered_bids.keys() for engine in self.engines)

    def event_tick(self, *, area):
        if area != self.owner:
            # We're connected to both areas but only want tick events from our owner
            return
        if area.current_tick % self.tick_ratio != 0:
            return

        for engine in self.engines:
            engine.tick(area=area)

    def event_trade(self, *, market, trade, offer=None):
        for engine in self.engines:
            engine.event_trade(trade=trade)

    def event_bid_traded(self, *, market, traded_bid):
        for engine in self.engines:
            engine.event_bid_traded(traded_bid=traded_bid)

    def event_bid_deleted(self, *, market, bid):
        for engine in self.engines:
            engine.event_bid_deleted(bid=bid)

    def event_offer_deleted(self, *, market, offer):
        for engine in self.engines:
            engine.event_offer_deleted(offer=offer)

    def event_offer_changed(self, *, market, existing_offer, new_offer):
        for engine in self.engines:
            engine.event_offer_changed(market=market,
                                       existing_offer=existing_offer,
                                       new_offer=new_offer)
