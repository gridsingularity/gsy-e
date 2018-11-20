import uuid
from logging import getLogger
from d3a.d3a_core.exceptions import BidNotFound, InvalidTrade
from d3a.models.market.market_structures import Bid, Trade
from d3a.events.event_structures import MarketEvent
from d3a.models.market.two_sided_pay_as_bid import TwoSidedPayAsBid

log = getLogger(__name__)


class TwoSidedPayAsClear(TwoSidedPayAsBid):

    def __init__(self, time_slot=None, area=None,
                 notification_listener=None, readonly=False):
        super().__init__(time_slot, area, notification_listener, readonly)

    def __repr__(self):  # pragma: no cover
        return "<TwoSidedPayAsClear{} offers: {} (E: {} kWh V: {}) trades: {} (E: {} kWh, V: {})>"\
            .format(" {}".format(self.time_slot_str),
                    len(self.offers),
                    sum(o.energy for o in self.offers.values()),
                    sum(o.price for o in self.offers.values()),
                    len(self.trades),
                    self.accumulated_trade_energy,
                    self.accumulated_trade_price
                    )

    def accept_clearing_bid(self,  clear_rate: int, bid: Bid, energy: float = None,
                            seller: str = None, buyer: str = None,
                            already_tracked: bool = False, price_drop: bool = True):
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
                residual_energy = market_bid.energy - energy
                residual_price = residual_energy * energy_rate
                self.bid(residual_price, residual_energy, buyer, seller, bid.id)
                bid = Bid(bid.id, (clear_rate * energy), energy,
                          buyer, seller, self)
            trade = Trade(str(uuid.uuid4()), self._now,
                          bid, seller, buyer, residual, price_drop=price_drop,
                          already_tracked=already_tracked)

            if not already_tracked:
                self._update_stats_after_trade(trade, bid, bid.buyer, already_tracked)
                log.warning(f"[TRADE][BID][{self.time_slot_str}] {trade}")

            self._notify_listeners(MarketEvent.BID_TRADED, bid_trade=trade)
            if not trade.residual:
                self._notify_listeners(MarketEvent.BID_DELETED, bid=market_bid)
            return trade
        else:
            raise Exception("Undefined state or conditions. Should never reach this place.")
