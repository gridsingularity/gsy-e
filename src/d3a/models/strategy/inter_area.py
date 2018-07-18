from collections import namedtuple
from typing import Dict, Set  # noqa

from d3a.exceptions import MarketException, OfferNotFoundException
from d3a.models.strategy.base import BaseStrategy, _TradeLookerUpper
from d3a.util import make_iaa_name


OfferInfo = namedtuple('OfferInfo', ('source_offer', 'target_offer'))
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
        self.traded_offers = set()  # type: Set[str]
        self.trade_residual = {}  # type Dict[str, Offer]
        self.ignored_offers = set()  # type: Set[str]

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

            trade_source = self.owner.accept_offer(
                self.markets.source,
                offer_info.source_offer,
                energy=trade.offer.energy,
                buyer=self.owner.name
            )
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
            self.offer_age.pop(offer_info.source_offer.id, None)
            self.traded_offers.add(offer_info.source_offer.id)
            self.traded_offers.add(offer_info.target_offer.id)

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

    def event_offer_deleted(self, *, market, offer):
        for engine in self.engines:
            engine.event_offer_deleted(offer=offer)

    def event_offer_changed(self, *, market, existing_offer, new_offer):
        for engine in self.engines:
            engine.event_offer_changed(market=market,
                                       existing_offer=existing_offer,
                                       new_offer=new_offer)
