from collections import namedtuple
from typing import Dict, Set  # noqa

from d3a.exceptions import MarketException, OfferNotFoundException, BidNotFound
from d3a.models.strategy.base import BaseStrategy, _TradeLookerUpper
from d3a.models.strategy.const import ConstSettings
from d3a.util import make_iaa_name, make_ba_name
from d3a import TIME_FORMAT
from d3a.models.market.market_structures import Bid

OfferInfo = namedtuple('OfferInfo', ('source_offer', 'target_offer'))
BidInfo = namedtuple('BidInfo', ('source_bid', 'target_bid'))
Markets = namedtuple('Markets', ('source', 'target'))
ResidualInfo = namedtuple('ResidualInfo', ('forwarded', 'age'))


class IAAEngine:
    def __init__(self, name: str, market_1, market_2, min_offer_age: int, transfer_fee_pct: int,
                 owner: "InterAreaAgent", balancing_agent):
        self.name = name
        self.markets = Markets(market_1, market_2)
        self.min_offer_age = min_offer_age
        self.transfer_fee_pct = transfer_fee_pct
        self.owner = owner
        self.balancing_agent = balancing_agent

        self.offer_age = {}  # type: Dict[str, int]
        # Offer.id -> OfferInfo
        self.forwarded_offers = {}  # type: Dict[str, OfferInfo]
        self.trade_residual = {}  # type Dict[str, Offer]
        self.ignored_offers = set()  # type: Set[str]

        self.forwarded_bids = {}  # type: Dict[str, BidInfo]

    def __repr__(self):
        return "<IAAEngine [{s.owner.name}] {s.name} {s.markets.source.time_slot:%H:%M}>".format(
            s=self
        )

    def _forward_offer(self, offer, offer_id):
        forwarded_offer = self.markets.target.offer(
            offer.price + (offer.price * (self.transfer_fee_pct / 100)),
            offer.energy,
            self.owner.name,
            self.balancing_agent
        )
        offer_info = OfferInfo(offer, forwarded_offer)
        self.forwarded_offers[forwarded_offer.id] = offer_info
        self.forwarded_offers[offer_id] = offer_info
        self.owner.log.debug(f"Forwarding offer {offer} to {forwarded_offer}")
        return forwarded_offer

    def _forward_bid(self, bid):
        if bid.buyer == self.markets.target.area.name and \
           bid.seller == self.markets.source.area.name:
            return
        if self.owner.name == self.markets.target.area.name:
            return
        forwarded_bid = self.markets.target.bid(
            bid.price + (bid.price * (self.transfer_fee_pct / 100)),
            bid.energy,
            self.owner.name,
            self.markets.target.area.name
        )
        bid_coupling = BidInfo(bid, forwarded_bid)
        self.forwarded_bids[forwarded_bid.id] = bid_coupling
        self.forwarded_bids[bid.id] = bid_coupling
        self.owner.log.debug(f"Forwarding bid {bid} to {forwarded_bid}")
        return forwarded_bid

    def _perform_pay_as_bid_matching(self):
        # Pay as bid first
        # There are 2 simplistic approaches to the problem
        # 1. Match the cheapest offer with the most expensive bid. This will favor the sellers
        # 2. Match the cheapest offer with the cheapest bid. This will favor the buyers,
        #    since the most affordable offers will be allocated for the most aggressive buyers.

        # Sorted bids in descending order
        sorted_bids = list(reversed(sorted(
            self.markets.source.bids.values(),
            key=lambda b: b.price / b.energy))
        )

        # Sorted offers in descending order
        sorted_offers = list(reversed(sorted(
            self.markets.source.offers.values(),
            key=lambda o: o.price / o.energy))
        )

        already_selected_bids = set()
        for offer in sorted_offers:
            for bid in sorted_bids:
                if bid.id not in already_selected_bids and \
                   offer.price / offer.energy <= bid.price / bid.energy and \
                   offer.seller != self.owner.name and \
                   offer.seller != bid.buyer:
                    already_selected_bids.add(bid.id)
                    yield bid, offer
                    break

    def _delete_forwarded_bid_entries(self, bid):
        bid_info = self.forwarded_bids.pop(bid.id, None)
        if not bid_info:
            return
        self.forwarded_bids.pop(bid_info.target_bid.id, None)
        self.forwarded_bids.pop(bid_info.source_bid.id, None)

    def _delete_forwarded_offer_entries(self, offer):
        offer_info = self.forwarded_offers.pop(offer.id, None)
        if not offer_info:
            return
        self.forwarded_offers.pop(offer_info.target_offer.id, None)
        self.forwarded_offers.pop(offer_info.source_offer.id, None)

    def _match_offers_bids(self):
        for bid, offer in self._perform_pay_as_bid_matching():
            selected_energy = bid.energy if bid.energy < offer.energy else offer.energy
            offer.price = offer.energy * (bid.price / bid.energy)
            self.owner.accept_offer(market=self.markets.source,
                                    offer=offer,
                                    buyer=self.owner.name,
                                    energy=selected_energy,
                                    price_drop=True)
            self._delete_forwarded_offer_entries(offer)

            self.markets.source.accept_bid(bid,
                                           selected_energy,
                                           seller=offer.seller,
                                           buyer=bid.buyer,
                                           already_tracked=True,
                                           price_drop=True)
            self._delete_forwarded_bid_entries(bid)

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
            self.owner.log.info("Offering %s", forwarded_offer)

        if ConstSettings.IAASettings.MARKET_TYPE == 2:
            for bid_id, bid in self.markets.source.bids.items():
                if bid_id not in self.forwarded_bids and \
                        self.owner.usable_bid(bid) and \
                        self.owner.name != bid.seller:
                    self._forward_bid(bid)

            self._match_offers_bids()

    def event_bid_traded(self, *, bid_trade):
        bid_info = self.forwarded_bids.get(bid_trade.offer.id)
        if not bid_info:
            return

        # Bid was traded in target market, buy in source
        if bid_trade.offer.id == bid_info.target_bid.id:
            source_price = bid_info.source_bid.price
            if bid_trade.price_drop:
                # Use the rate of the trade bid for accepting the source bid too
                source_price = bid_trade.offer.price
                # Drop the rate of the trade bid according to IAA fee
                source_price = source_price / (1 + (self.transfer_fee_pct / 100))

            self.markets.source.accept_bid(
                bid_info.source_bid._replace(price=source_price, energy=bid_trade.offer.energy),
                energy=bid_trade.offer.energy,
                seller=self.owner.name,
                already_tracked=False
            )
            if not bid_trade.residual:
                self._delete_forwarded_bid_entries(bid_info.target_bid)

        # Bid was traded in the source market by someone else
        elif bid_trade.offer.id == bid_info.source_bid.id:
            if self.owner.name == bid_trade.seller:
                return
            # Delete target bid
            try:
                self.markets.target.delete_bid(bid_info.target_bid)
            except BidNotFound:
                pass
            self._delete_forwarded_bid_entries(bid_info.source_bid)
        else:
            raise Exception(f"Invalid bid state for IAA {self.owner.name}: "
                            f"traded bid {bid_trade} was not in offered bids tuple {bid_info}")

    def event_trade(self, *, trade):
        offer_info = self.forwarded_offers.get(trade.offer.id)
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
                if trade.price_drop:
                    # Use the rate of the trade offer for accepting the source offer too
                    # Drop the rate of the trade offer according to IAA fee
                    trade_offer_rate = trade.offer.price / trade.offer.energy
                    offer_info.source_offer.price = \
                        trade_offer_rate * offer_info.source_offer.energy \
                        / (1 + (self.transfer_fee_pct / 100))
                trade_source = self.owner.accept_offer(
                    self.markets.source,
                    offer_info.source_offer,
                    energy=trade.offer.energy,
                    buyer=self.owner.name
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

    def event_bid_deleted(self, *, bid):

        bid_id = bid.id if isinstance(bid, Bid) else bid
        bid_info = self.forwarded_bids.get(bid_id)

        if not bid_info:
            # Deletion doesn't concern us
            return

        if bid_info.source_bid.id == bid_id:
            # Bid in source market of an bid we're already offering in the target market
            # was deleted - also delete in target market
            try:
                self.markets.target.delete_bid(bid_info.target_bid.id)
                self._delete_forwarded_bid_entries(bid_info.target_bid)
            except BidNotFound:
                self.owner.log.debug(f"Bid {bid_info.target_bid.id} not "
                                     f"found in the target market.")
            except MarketException:
                self.owner.log.exception("Error deleting InterAreaAgent offer")
        self._delete_forwarded_bid_entries(bid_info.source_bid)

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

            self.owner.log.info("Offer %s changed to residual offer %s",
                                offer_info.target_offer,
                                forwarded)

            # Do not delete the forwarded offer entries for the case of residual offers
            if existing_offer.seller != new_offer.seller:
                self._delete_forwarded_offer_entries(offer_info.source_offer)


class InterAreaAgent(BaseStrategy):
    parameters = ('owner', 'higher_market', 'lower_market', 'transfer_fee_pct',
                  'min_offer_age')

    def __init__(self, *, owner, higher_market, lower_market,
                 transfer_fee_pct=1, min_offer_age=1, balancing_agent=False):
        """
        Equalize markets

        :param higher_market:
        :type higher_market: Market
        :param lower_market:
        :type lower_market: Market
        :param min_offer_age: Minimum age of offer before transferring
        """
        super().__init__()
        self.owner = owner
        self.name = make_iaa_name(owner)
        self.balancing_agent = balancing_agent

        self.engines = [
            IAAEngine('High -> Low', higher_market, lower_market, min_offer_age, transfer_fee_pct,
                      self, balancing_agent),
            IAAEngine('Low -> High', lower_market, higher_market, min_offer_age, transfer_fee_pct,
                      self, balancing_agent),
        ]

        self.time_slot = higher_market.time_slot.strftime(TIME_FORMAT)

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
        return all(offer.id not in engine.forwarded_offers.keys() for engine in self.engines)

    def usable_bid(self, bid):
        """Prevent IAAEngines from trading their counterpart's bids"""
        return all(bid.id not in engine.forwarded_bids.keys() for engine in self.engines)

    def _get_market_from_market_id(self, market_id):
        if self.lower_market.id == market_id:
            return self.lower_market
        elif self.higher_market.id == market_id:
            return self.higher_market
        elif self.owner.get_future_market_from_id(market_id):
            return self.owner.get_future_market_from_id(market_id)
        elif self.owner.parent.get_future_market_from_id(market_id) is not None:
            return self.owner.parent.get_future_market_from_id(market_id)
        else:
            return None

    def event_tick(self, *, area):
        if area != self.owner:
            # We're connected to both areas but only want tick events from our owner
            return

        for engine in self.engines:
            engine.tick(area=area)

    def event_trade(self, *, market_id, trade):
        for engine in self.engines:
            engine.event_trade(trade=trade)

    def event_bid_traded(self, *, market_id, bid_trade):
        for engine in self.engines:
            engine.event_bid_traded(bid_trade=bid_trade)

    def event_bid_deleted(self, *, market_id, bid):
        for engine in self.engines:
            engine.event_bid_deleted(bid=bid)

    def event_offer_deleted(self, *, market_id, offer):
        for engine in self.engines:
            engine.event_offer_deleted(offer=offer)

    def event_offer_changed(self, *, market_id, existing_offer, new_offer):
        for engine in self.engines:
            engine.event_offer_changed(market_id=market_id,
                                       existing_offer=existing_offer,
                                       new_offer=new_offer)


class BalancingAgent(InterAreaAgent):

    def __init__(self, owner, higher_market, lower_market,
                 transfer_fee_pct=1, min_offer_age=1):
        self.balancing_spot_trade_ratio = owner.balancing_spot_trade_ratio
        InterAreaAgent.__init__(self, owner=owner, higher_market=higher_market,
                                lower_market=lower_market, transfer_fee_pct=transfer_fee_pct,
                                min_offer_age=min_offer_age, balancing_agent=True)
        self.name = make_ba_name(self.owner)

    def event_tick(self, *, area):
        super().event_tick(area=area)
        if self.lower_market.unmatched_energy_downward > 0.0 or \
                self.lower_market.unmatched_energy_upward > 0.0:
            self._trigger_balancing_trades(self.lower_market.unmatched_energy_upward,
                                           self.lower_market.unmatched_energy_downward)

    def event_trade(self, *, market_id, trade):
        market = self._get_market_from_market_id(market_id)
        if market is None:
            return

        self._calculate_and_buy_balancing_energy(market, trade)
        super().event_trade(market_id=market_id, trade=trade)

    def event_bid_traded(self, *, market_id, bid_trade):
        if bid_trade.already_tracked:
            return

        market = self._get_market_from_market_id(market_id)
        if market is None:
            return

        self._calculate_and_buy_balancing_energy(market, bid_trade)
        super().event_bid_traded(market_id=market_id, bid_trade=bid_trade)

    def _calculate_and_buy_balancing_energy(self, market, trade):
        if trade.buyer != make_iaa_name(self.owner) or \
                market.time_slot != self.lower_market.time_slot:
            return
        positive_balancing_energy = \
            trade.offer.energy * self.balancing_spot_trade_ratio + \
            self.lower_market.unmatched_energy_upward
        negative_balancing_energy = \
            trade.offer.energy * self.balancing_spot_trade_ratio + \
            self.lower_market.unmatched_energy_downward

        self._trigger_balancing_trades(positive_balancing_energy, negative_balancing_energy)

    def _trigger_balancing_trades(self, positive_balancing_energy, negative_balancing_energy):
        for offer in self.lower_market.sorted_offers:
            if offer.energy > 0 and positive_balancing_energy > 0:
                balance_trade = self._balancing_trade(offer,
                                                      positive_balancing_energy)
                if balance_trade is not None:
                    positive_balancing_energy -= abs(balance_trade.offer.energy)
            elif offer.energy < 0 and negative_balancing_energy > 0:
                balance_trade = self._balancing_trade(offer,
                                                      -negative_balancing_energy)
                if balance_trade is not None:
                    negative_balancing_energy -= abs(balance_trade.offer.energy)

        self.lower_market.unmatched_energy_upward = positive_balancing_energy
        self.lower_market.unmatched_energy_downward = negative_balancing_energy

    def _balancing_trade(self, offer, target_energy):
        trade = None
        buyer = make_ba_name(self.owner) \
            if make_ba_name(self.owner) != offer.seller \
            else f"{self.owner.name} Reserve"
        if abs(offer.energy) <= abs(target_energy):
            trade = self.lower_market.accept_offer(offer_or_id=offer,
                                                   buyer=buyer,
                                                   energy=offer.energy)
        elif abs(offer.energy) >= abs(target_energy):
            trade = self.lower_market.accept_offer(offer_or_id=offer,
                                                   buyer=buyer,
                                                   energy=target_energy)
        return trade

    def event_balancing_trade(self, *, market_id, trade, offer=None):
        for engine in self.engines:
            engine.event_trade(trade=trade)

    def event_balancing_offer_changed(self, *, market_id, existing_offer, new_offer):
        for engine in self.engines:
            engine.event_offer_changed(market_id=market_id,
                                       existing_offer=existing_offer,
                                       new_offer=new_offer)
