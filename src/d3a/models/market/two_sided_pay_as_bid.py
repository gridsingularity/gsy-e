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
import uuid
from typing import Union  # noqa
from logging import getLogger

from d3a.models.market.one_sided import OneSidedMarket
from d3a.d3a_core.exceptions import BidNotFound, InvalidBid, InvalidTrade, ChainTradeException
from d3a.models.market.market_structures import Bid, Trade
from d3a.events.event_structures import MarketEvent
from d3a.constants import FLOATING_POINT_TOLERANCE

log = getLogger(__name__)


class TwoSidedPayAsBid(OneSidedMarket):

    def __init__(self, time_slot=None, area=None, notification_listener=None, readonly=False):
        super().__init__(time_slot, area, notification_listener, readonly)

    def __repr__(self):  # pragma: no cover
        return "<TwoSidedPayAsBid{} bids: {} (E: {} kWh V:{}) " \
               "offers: {} (E: {} kWh V: {}) trades: {} (E: {} kWh, V: {})>"\
            .format(" {}".format(self.time_slot_str),
                    len(self.bids),
                    sum(b.energy for b in self.bids.values()),
                    sum(b.price for b in self.bids.values()),
                    len(self.offers),
                    sum(o.energy for o in self.offers.values()),
                    sum(o.price for o in self.offers.values()),
                    len(self.trades),
                    self.accumulated_trade_energy,
                    self.accumulated_trade_price
                    )

    def bid(self, price: float, energy: float, buyer: str, seller: str, bid_id: str=None) -> Bid:
        if energy <= 0:
            raise InvalidBid()

        price = price * (1 - self.transfer_fee_ratio) - self.transfer_fee_const * energy
        bid = Bid(str(uuid.uuid4()) if bid_id is None else bid_id,
                  price, energy, buyer, seller, self)
        self.bids[bid.id] = bid
        self.bid_history.append(bid)
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
                   trade_rate: float = None, iaa_fee: bool = False):
        if iaa_fee and trade_rate is None:
            raise ChainTradeException()
        market_bid = self.bids.pop(bid.id, None)
        if market_bid is None:
            raise BidNotFound("During accept bid: " + str(bid))

        seller = market_bid.seller if seller is None else seller
        buyer = market_bid.buyer if buyer is None else buyer
        energy = market_bid.energy if energy is None else energy
        if trade_rate is None:
            trade_rate = market_bid.price / market_bid.energy
        assert trade_rate <= (market_bid.price / market_bid.energy) + FLOATING_POINT_TOLERANCE, \
            f"trade rate: {trade_rate} market {market_bid.price / market_bid.energy}"
        if iaa_fee:
            source_rate = trade_rate / (1 - self.transfer_fee_ratio) + self.transfer_fee_const
            self._grid_fee += (trade_rate - source_rate) * energy
        else:
            source_rate = trade_rate

        if energy <= 0:
            raise InvalidTrade("Energy cannot be zero.")
        elif energy > market_bid.energy:
            raise InvalidTrade("Traded energy cannot be more than the bid energy.")
        elif energy is None or energy <= market_bid.energy:
            residual = False
            if energy is not None and energy < market_bid.energy:
                # Partial bidding

                # For the residual bid we use the market rate, in order to not affect
                # rate increase algorithm.
                energy_rate = market_bid.price / market_bid.energy
                residual_energy = market_bid.energy - energy
                residual_price = residual_energy * energy_rate
                changed_bid = self.bid(residual_price, residual_energy, buyer, seller)
                self._notify_listeners(MarketEvent.BID_CHANGED,
                                       existing_bid=bid, new_bid=changed_bid)
                residual = changed_bid
                # For the accepted bid we use the 'clearing' rate from the bid
                # input argument.
                final_price = energy * source_rate
                bid = Bid(bid.id, final_price, energy, buyer, seller, self)
            else:
                if trade_rate is not None:
                    bid = bid._replace(price=source_rate * market_bid.energy)
            trade = Trade(str(uuid.uuid4()), self._now, bid, seller,
                          buyer, residual, already_tracked=already_tracked)

            if not already_tracked:
                self._update_stats_after_trade(trade, bid, bid.buyer, already_tracked)
                log.warning(f"[TRADE][BID][{self.time_slot_str}] {trade}")

            self._notify_listeners(MarketEvent.BID_TRADED, bid_trade=trade)
            if not trade.residual:
                self._notify_listeners(MarketEvent.BID_DELETED, bid=market_bid)
            return trade
        else:
            raise Exception("Undefined state or conditions. Should never reach this place.")
