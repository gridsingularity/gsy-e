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

from copy import deepcopy
from logging import getLogger
from typing import Dict, List, Union, Optional, Tuple, TYPE_CHECKING

from gsy_framework.constants_limits import ConstSettings, GlobalConfig, DATE_TIME_FORMAT
from gsy_framework.data_classes import Bid, Offer, Trade, BaseBidOffer, TradeBidOfferInfo
from pendulum import DateTime, duration

from gsy_e.gsy_e_core.blockchain_interface import NonBlockchainInterface
from gsy_e.gsy_e_core.util import is_time_slot_in_simulation_duration
from gsy_e.models.market import GridFee
from gsy_e.models.market import lock_market_action
from gsy_e.models.market.two_sided import TwoSidedMarket

if TYPE_CHECKING:
    from gsy_e.models.area.event_dispatcher import AreaDispatcher
    from gsy_e.models.config import SimulationConfig

log = getLogger(__name__)


class FutureMarketException(Exception):
    """Exception specific to the Future markets."""


class FutureMarkets(TwoSidedMarket):
    """Class responsible for future markets."""

    def __init__(self, bc: Optional[NonBlockchainInterface] = None,
                 notification_listener: Optional["AreaDispatcher"] = None,
                 readonly: bool = False,
                 grid_fee_type: int = ConstSettings.MASettings.GRID_FEE_TYPE,
                 grid_fees: Optional[GridFee] = None,
                 name: Optional[str] = None) -> None:
        super().__init__(time_slot=None, bc=bc, notification_listener=notification_listener,
                         readonly=readonly, grid_fee_type=grid_fee_type,
                         grid_fees=grid_fees, name=name, in_sim_duration=True)

        self.slot_bid_mapping: Dict[DateTime, List[Bid]] = {}
        self.slot_offer_mapping: Dict[DateTime, List[Offer]] = {}
        self.slot_trade_mapping: Dict[DateTime, List[Trade]] = {}

    def __repr__(self):  # pragma: no cover
        return (f"<{self._class_name} bids:{self.slot_bid_mapping}"
                f"offer: {self.slot_offer_mapping} trades: {self.slot_trade_mapping}>")

    @property
    def _debug_log_market_type_identifier(self) -> str:
        return "[FUTURE]"

    @property
    def market_time_slots(self) -> List[DateTime]:
        """Return list of all time slots of future markets."""
        return list(self.slot_bid_mapping.keys())

    def open_bids_and_offers(self, **kwargs) -> Tuple[List, List]:
        if kwargs.get("time_slot") is None:
            return [], []

        return (self.slot_bid_mapping[kwargs["time_slot"]],
                self.slot_offer_mapping[kwargs["time_slot"]])

    def orders_per_slot(self) -> Dict[str, Dict]:
        """Return all orders in the market per time slot."""
        orders_dict = {}
        for time_slot, bids_list in self.slot_bid_mapping.items():
            time_slot = time_slot.format(DATE_TIME_FORMAT)
            if time_slot not in orders_dict:
                orders_dict[time_slot] = {"bids": [], "offers": []}
            orders_dict[time_slot]["bids"].extend([bid.serializable_dict() for bid in bids_list])
        for time_slot, offers_list in self.slot_offer_mapping.items():
            time_slot = time_slot.format(DATE_TIME_FORMAT)
            if time_slot not in orders_dict:
                orders_dict[time_slot] = {"bids": [], "offers": []}
            orders_dict[time_slot]["offers"].extend(
                [offer.serializable_dict() for offer in offers_list])
        return orders_dict

    @staticmethod
    def _remove_old_orders_from_list(order_list: List, current_market_time_slot: DateTime) -> List:
        return [
            order for order in order_list if order.time_slot > current_market_time_slot
        ]

    @staticmethod
    def _remove_old_orders_from_dict(order_dict: Dict, current_market_time_slot: DateTime) -> Dict:
        return {
            order_id: order
            for order_id, order in order_dict.items()
            if order.time_slot > current_market_time_slot
        }

    def delete_orders_in_old_future_markets(self, current_market_time_slot: DateTime) -> None:
        """Delete order and trade buffers."""
        self._delete_order_dict_market_slot(current_market_time_slot,
                                            self.slot_bid_mapping, Bid)
        self._delete_order_dict_market_slot(current_market_time_slot,
                                            self.slot_offer_mapping, Offer)
        self._delete_order_dict_market_slot(current_market_time_slot,
                                            self.slot_trade_mapping, Trade)

        self.offer_history = self._remove_old_orders_from_list(
            self.offer_history, current_market_time_slot)
        self.bid_history = self._remove_old_orders_from_list(
            self.bid_history, current_market_time_slot)

    def _delete_order_dict_market_slot(self, current_market_time_slot: DateTime,
                                       order_dict:
                                       Dict[DateTime, List[Union[BaseBidOffer, Trade]]],
                                       order_type: Union[BaseBidOffer, Trade]) -> None:
        """Empty order_dicts of order and trades for non-future time_stamps."""
        delete_time_slots = []
        for time_slot, orders in order_dict.items():
            if time_slot <= current_market_time_slot:
                self._delete_list_of_orders_from_market(orders, order_type)
                delete_time_slots.append(time_slot)
        for time_slot in delete_time_slots:
            del order_dict[time_slot]

    def _delete_list_of_orders_from_market(self, delete_orders: List,
                                           order_type: Union[BaseBidOffer, Trade]) -> None:
        """Delete orders/trades from traditional market order dicts."""
        if order_type == Trade:
            current_market_trades = self.trades
            for trade in delete_orders:
                current_market_trades.remove(trade)
                del trade
        else:
            current_market_orders = self.offers if order_type is Offer else self.bids
            for order in delete_orders:
                current_market_orders.pop(order.id, None)

    def create_future_markets(self, current_market_time_slot: DateTime,
                              slot_length: duration,
                              config: "SimulationConfig") -> None:
        """Add sub dicts in order dictionaries for future market slots."""
        future_time_slot = current_market_time_slot.add(minutes=slot_length.total_minutes())
        most_future_slot = future_time_slot + GlobalConfig.future_market_duration
        while future_time_slot <= most_future_slot:
            if (future_time_slot not in self.slot_bid_mapping and
                    is_time_slot_in_simulation_duration(config, future_time_slot)):
                self.slot_bid_mapping[future_time_slot] = []
                self.slot_offer_mapping[future_time_slot] = []
                self.slot_trade_mapping[future_time_slot] = []
            future_time_slot = future_time_slot.add(minutes=slot_length.total_minutes())

    @lock_market_action
    def get_bids_per_slot(self, time_slot: DateTime) -> List[Bid]:
        """Return list of bids for a specific market slot."""
        return deepcopy(self.slot_bid_mapping[time_slot])

    @lock_market_action
    def get_offers_per_slot(self, time_slot: DateTime) -> List[Offer]:
        """Return list of offers for a specific market slot."""
        return deepcopy(self.slot_offer_mapping[time_slot])

    @lock_market_action
    def bid(self, price: float, energy: float, buyer: str, buyer_origin: str,
            bid_id: Optional[str] = None,
            original_price: Optional[float] = None,
            adapt_price_with_fees: bool = True,
            add_to_history: bool = True,
            buyer_origin_id: Optional[str] = None,
            buyer_id: Optional[str] = None,
            attributes: Optional[Dict] = None,
            requirements: Optional[List[Dict]] = None,
            time_slot: Optional[DateTime] = None) -> Bid:
        """Call superclass bid and buffer returned bid object."""
        if not time_slot:
            raise FutureMarketException("time_slot parameter was not provided for bid "
                                        "method in future markets.")
        bid = super().bid(price=price, energy=energy, buyer=buyer, buyer_origin=buyer_origin,
                          bid_id=bid_id, original_price=original_price,
                          add_to_history=True, adapt_price_with_fees=adapt_price_with_fees,
                          buyer_origin_id=buyer_origin_id, buyer_id=buyer_id,
                          attributes=attributes, requirements=requirements, time_slot=time_slot)
        self.slot_bid_mapping[time_slot].append(bid)
        return bid

    @lock_market_action
    def offer(self, price: float, energy: float, seller: str, seller_origin: str,
              offer_id: Optional[str] = None,
              original_price: Optional[float] = None,
              dispatch_event: bool = True,
              adapt_price_with_fees: bool = True,
              add_to_history: bool = True,
              seller_origin_id: Optional[str] = None,
              seller_id: Optional[str] = None,
              attributes: Optional[Dict] = None,
              requirements: Optional[List[Dict]] = None,
              time_slot: Optional[DateTime] = None) -> Offer:
        """Call superclass offer and buffer returned offer object."""
        if not time_slot:
            raise FutureMarketException("time_slot parameter was not provided for offer "
                                        "method in future markets.")
        offer = super().offer(price, energy, seller, seller_origin, offer_id, original_price,
                              dispatch_event, adapt_price_with_fees, add_to_history,
                              seller_origin_id, seller_id, attributes, requirements, time_slot)
        self.slot_offer_mapping[time_slot].append(offer)
        return offer

    def delete_bid(self, bid_or_id: Union[str, Bid]) -> None:
        """Delete bid object from all buffers."""
        bid = bid_or_id if isinstance(bid_or_id, Bid) else self.bids.get(bid_or_id)
        if bid:
            self.slot_bid_mapping[bid.time_slot].remove(bid)
        super().delete_bid(bid_or_id)

    def delete_offer(self, offer_or_id: Union[str, Offer]) -> None:
        """Delete offer object from all buffers."""
        offer = offer_or_id if isinstance(offer_or_id, Offer) else self.offers.get(offer_or_id)
        if offer:
            self.slot_offer_mapping[offer.time_slot].remove(offer)
        super().delete_offer(offer_or_id)

    def accept_bid(self, bid: Bid,
                   energy: Optional[float] = None,
                   seller: Optional[str] = None,
                   buyer: Optional[str] = None,
                   already_tracked: bool = False,
                   trade_rate: Optional[float] = None,
                   trade_offer_info: Optional[TradeBidOfferInfo] = None,
                   seller_origin: Optional[str] = None,
                   seller_origin_id: Optional[str] = None,
                   seller_id: Optional[str] = None) -> Trade:
        """Call superclass accept_bid and buffer returned trade object."""
        trade = super().accept_bid(bid=bid, energy=energy, seller=seller, buyer=buyer,
                                   already_tracked=already_tracked, trade_rate=trade_rate,
                                   trade_offer_info=trade_offer_info, seller_origin=seller_origin,
                                   seller_origin_id=seller_origin_id, seller_id=seller_id)

        if bid.id not in self.bids:
            self.slot_bid_mapping[bid.time_slot].remove(bid)

        if already_tracked is False:
            self.slot_trade_mapping[trade.time_slot].append(trade)
        return trade

    def accept_offer(self, offer_or_id: Union[str, Offer], buyer: str, *,
                     energy: Optional[float] = None,
                     already_tracked: bool = False,
                     trade_rate: Optional[float] = None,
                     trade_bid_info: Optional[TradeBidOfferInfo] = None,
                     buyer_origin: Optional[str] = None,
                     buyer_origin_id: Optional[str] = None,
                     buyer_id: Optional[str] = None) -> Trade:
        """Call superclass accept_offer and buffer returned trade object."""

        if isinstance(offer_or_id, Offer):
            offer_or_id = offer_or_id.id
        offer = self.offers.get(offer_or_id, None)

        trade = super().accept_offer(offer_or_id=offer_or_id,
                                     buyer=buyer, energy=energy,
                                     already_tracked=already_tracked, trade_rate=trade_rate,
                                     trade_bid_info=trade_bid_info, buyer_origin=buyer_origin,
                                     buyer_origin_id=buyer_origin_id, buyer_id=buyer_id)

        if offer.id not in self.offers:
            self.slot_offer_mapping[offer.time_slot].remove(offer)

        if already_tracked is False:
            self.slot_trade_mapping[trade.time_slot].append(trade)
        return trade
