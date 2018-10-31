import uuid
from typing import Dict, List, Set, Union  # noqa
from logging import getLogger

from d3a.models.market.one_sided import OneSidedMarket
from d3a.exceptions import BidNotFound, InvalidBid, InvalidTrade
from d3a.models.market.market_structures import Bid, Trade
from d3a.models.events import MarketEvent

log = getLogger(__name__)


class TwoSidedPayAsBid(OneSidedMarket):

    def __init__(self, time_slot=None, area=None, notification_listener=None, readonly=False):
        super().__init__(time_slot, area, notification_listener, readonly)

    def bid(self, price: float, energy: float, buyer: str, seller: str, bid_id: str=None) -> Bid:
        if energy <= 0:
            raise InvalidBid()
        bid = Bid(str(uuid.uuid4()) if bid_id is None else bid_id,
                  price, energy, buyer, seller, self)
        self.bids[bid.id] = bid
        log.info(f"[BID][NEW][{self.time_slot_str}] {bid}")
        return bid

    def delete_bid(self, bid_or_id: Union[str, Bid]):
        if isinstance(bid_or_id, Bid):
            bid_or_id = bid_or_id.id
        bid = self.bids.pop(bid_or_id, None)
        if not bid:
            raise BidNotFound(bid_or_id)
        log.info(f"[BID][DEL][{self.time_slot_str}] {bid}")
        self._notify_listeners(MarketEvent.BID_DELETED, bid=bid)

    def accept_bid(self, bid: Bid, energy: float = None,
                   seller: str = None, buyer: str = None, already_tracked: bool = False,
                   price_drop: bool = True):
        market_bid = self.bids.pop(bid.id, None)
        if market_bid is None:
            raise BidNotFound("During accept bid: " + str(bid))

        seller = market_bid.seller if seller is None else seller
        buyer = market_bid.buyer if buyer is None else buyer
        energy = market_bid.energy if energy is None else energy
        if energy <= 0:
            raise InvalidTrade("Energy cannot be zero.")
        elif energy > bid.energy:
            raise InvalidTrade("Traded energy cannot be more than the bid energy.")
        elif energy is None or energy <= market_bid.energy:
            residual = False
            if energy < market_bid.energy:
                # Partial bidding
                residual = True
                energy_rate = market_bid.price / market_bid.energy
                final_price = energy * energy_rate
                residual_energy = market_bid.energy - energy
                residual_price = residual_energy * energy_rate
                self.bid(residual_price, residual_energy, buyer, seller, bid.id)
                bid = Bid(bid.id, final_price, energy,
                          buyer, seller, self)

            trade = Trade(str(uuid.uuid4()), self._now,
                          bid, seller, buyer, residual, price_drop=price_drop,
                          already_tracked=already_tracked)
            self._update_stats_after_trade(trade, bid, bid.buyer, already_tracked)
            if not already_tracked:
                log.warning(f"[TRADE][BID][{self.time_slot_str}] {trade}")

            self._notify_listeners(MarketEvent.BID_TRADED, bid_trade=trade)
            if not trade.residual:
                self._notify_listeners(MarketEvent.BID_DELETED, bid=market_bid)
            return trade
        else:
            raise Exception("Undefined state or conditions. Should never reach this place.")
