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

import json
import logging
import sys
from abc import ABC
from dataclasses import dataclass
from logging import getLogger
from typing import TYPE_CHECKING, Callable, Dict, Generator, List, Optional, Union
from uuid import uuid4

from gsy_framework.constants_limits import ConstSettings
from gsy_framework.data_classes import Bid, Offer, Trade, TraderDetails
from gsy_framework.enums import SpotMarketTypeEnum
from gsy_framework.utils import limit_float_precision
from pendulum import DateTime

from gsy_e import constants
from gsy_e.constants import FLOATING_POINT_TOLERANCE, REDIS_PUBLISH_RESPONSE_TIMEOUT
from gsy_e.events import EventMixin
from gsy_e.events.event_structures import AreaEvent, MarketEvent
from gsy_e.gsy_e_core.device_registry import DeviceRegistry
from gsy_e.gsy_e_core.exceptions import D3ARedisException, MarketException, SimulationException
from gsy_e.gsy_e_core.redis_connections.area_market import BlockingCommunicator
from gsy_e.gsy_e_core.util import append_or_create_key
from gsy_e.models.base import AreaBehaviorBase
from gsy_e.models.config import SimulationConfig
from gsy_e.models.market import MarketBase
from gsy_e.models.strategy.future.strategy import FutureMarketStrategyInterface
from gsy_e.models.strategy.settlement.strategy import SettlementMarketStrategyInterface

log = getLogger(__name__)


if TYPE_CHECKING:
    from gsy_framework.data_classes import TradeBidOfferInfo

    from gsy_e.models.market.one_sided import OneSidedMarket
    from gsy_e.models.market.two_sided import TwoSidedMarket

INF_ENERGY = int(sys.maxsize)


# pylint: disable=too-many-instance-attributes
@dataclass
class AcceptOfferParameters:
    """Parameters for the accept_offer MarketStrategyConnectionAdapter methods"""

    market: Union["OneSidedMarket", str]
    offer: Offer
    buyer: TraderDetails
    energy: float
    trade_bid_info: "TradeBidOfferInfo"

    def to_dict(self) -> dict:
        """Convert dataclass to dict in order to be able to send these arguments via Redis."""
        return {
            "offer_or_id": self.offer.to_json_string(),
            "buyer": self.buyer.serializable_dict(),
            "energy": self.energy,
            "trade_bid_info": self.trade_bid_info.serializable_dict(),
        }

    def accept_offer_using_market_object(self) -> Trade:
        """Calls accept offer on the market object that is contained in the dataclass,
        using the arguments from the other dataclass members"""
        return self.market.accept_offer(
            offer_or_id=self.offer,
            buyer=self.buyer,
            energy=self.energy,
            trade_bid_info=self.trade_bid_info,
        )


class _TradeLookerUpper:
    """Find trades that concern the strategy from the selected market"""

    def __init__(self, owner_name: str):
        self.owner_name = owner_name

    def __getitem__(self, market: MarketBase) -> Generator[Trade, None, None]:
        for trade in market.trades:
            owner_name = self.owner_name
            if owner_name in (trade.seller.name, trade.buyer.name):
                yield trade


def market_strategy_connection_adapter_factory() -> (
    Union["MarketStrategyConnectionAdapter", "MarketStrategyConnectionRedisAdapter"]
):
    """
    Return an object of either MarketStrategyConnectionRedisAdapter or
    MarketStrategyConnectionAdapter, depending on whether the flag EVENT_DISPATCHING_VIA_REDIS is
    enabled.
    Returns: Instance of the market strategy connection adapter

    """
    if ConstSettings.GeneralSettings.EVENT_DISPATCHING_VIA_REDIS:
        return MarketStrategyConnectionRedisAdapter()
    return MarketStrategyConnectionAdapter()


class MarketStrategyConnectionRedisAdapter:
    """
    Adapter to the Redis market interface. Send commands to the market via Redis and not calling
    the class methods. Useful for markets that are run in a remote service, different from
    the strategy.
    """

    def __init__(self):
        self.redis = BlockingCommunicator()
        self._trade_buffer: Optional[Trade] = None
        self._offer_buffer: Optional[Offer] = None
        self._event_response_uuids: List[str] = []

    def offer(self, market: Union["OneSidedMarket", str], offer_args: dict) -> Offer:
        """
        Send offer to a market through Redis.
        Args:
            market: Market that the offer will be posted to. Accepts either a Market object or its
                    id as a string
            offer_args: Dict that contains the parameters of the offer

        Returns: Offer object that is posted on the market

        """
        market_id = market.id if not isinstance(market, str) else market
        self._send_events_to_market("OFFER", market_id, offer_args, self._redis_offer_response)
        offer = self._offer_buffer
        assert offer is not None
        self._offer_buffer = None
        return offer

    def accept_offer(self, offer_parameters: AcceptOfferParameters) -> Trade:
        """Accept an offer on a market via Redis."""
        market_id = (
            offer_parameters.market.id
            if not isinstance(offer_parameters.market, str)
            else offer_parameters.market
        )

        self._send_events_to_market(
            "ACCEPT_OFFER",
            market_id,
            offer_parameters.to_dict(),
            self._redis_accept_offer_response,
        )
        trade = self._trade_buffer
        self._trade_buffer = None
        assert trade is not None
        return trade

    def _redis_accept_offer_response(self, payload: dict):
        data = json.loads(payload["data"])
        if data["status"] == "ready":
            self._trade_buffer = Trade.from_json(data["trade"])
            self._event_response_uuids.append(data["transaction_uuid"])
        else:
            raise D3ARedisException(
                f"Error when receiving response on channel {payload['channel']}:: "
                f"{data['exception']}:  {data['error_message']} {data}"
            )

    def delete_offer(self, market: Union["OneSidedMarket", str], offer: Offer) -> None:
        """Delete offer from a market"""
        market_id = market.id if not isinstance(market, str) else market
        data = {"offer_or_id": offer.to_json_string()}
        self._send_events_to_market(
            "DELETE_OFFER", market_id, data, self._redis_delete_offer_response
        )

    def _send_events_to_market(
        self,
        event_type_str: str,
        market_id: Union[str, MarketBase],
        data: dict,
        callback: Callable,
    ) -> None:
        if not isinstance(market_id, str):
            market_id = market_id.id
        response_channel = f"{market_id}/{event_type_str}/RESPONSE"
        market_channel = f"{market_id}/{event_type_str}"

        data["transaction_uuid"] = str(uuid4())
        self.redis.sub_to_channel(response_channel, callback)
        self.redis.publish(market_channel, json.dumps(data))

        def event_response_was_received_callback():
            return data["transaction_uuid"] in self._event_response_uuids

        self.redis.poll_until_response_received(event_response_was_received_callback)

        if data["transaction_uuid"] not in self._event_response_uuids:
            logging.error(
                "Transaction ID not found after %s seconds: %s",
                REDIS_PUBLISH_RESPONSE_TIMEOUT,
                data,
            )
        else:
            self._event_response_uuids.remove(data["transaction_uuid"])

    def _redis_delete_offer_response(self, payload: dict) -> None:
        data = json.loads(payload["data"])
        if data["status"] == "ready":
            self._event_response_uuids.append(data["transaction_uuid"])

        else:
            raise D3ARedisException(
                f"Error when receiving response on channel {payload['channel']}:: "
                f"{data['exception']}:  {data['error_message']}"
            )

    def _redis_offer_response(self, payload):
        data = json.loads(payload["data"])
        if data["status"] == "ready":
            self._offer_buffer = Offer.from_json(data["offer"])
            self._event_response_uuids.append(data["transaction_uuid"])
        else:
            raise D3ARedisException(
                f"Error when receiving response on channel {payload['channel']}:: "
                f"{data['exception']}:  {data['error_message']}"
            )


class MarketStrategyConnectionAdapter:
    """
    Adapter to the MarketBase class. Used by default when accessing the market object directly and
    not via Redis.
    """

    @staticmethod
    def accept_offer(offer_parameters: AcceptOfferParameters) -> Trade:
        """Accept an offer on a market."""
        return offer_parameters.accept_offer_using_market_object()

    @staticmethod
    def delete_offer(market: "OneSidedMarket", offer: Offer) -> None:
        """Delete offer from a market"""
        market.delete_offer(offer)

    @staticmethod
    def offer(market: "OneSidedMarket", **offer_kwargs) -> Offer:
        """Post offer to the market"""
        return market.offer(**offer_kwargs)


class Offers:
    """
    Keep track of a strategy's accepted and own offers.

    When writing a strategy class, use the post(), remove() and
    replace() methods to keep track of offers.

    posted_in_market() yields all offers that have been posted,
    open_in_market() only those who have not been sold.
    """

    def __init__(self, strategy: "BaseStrategy"):
        self.strategy = strategy
        self.bought = {}  # type: Dict[Offer, str]
        self.posted = {}  # type: Dict[Offer, str]
        self.sold = {}  # type: Dict[str, List[Offer]]
        self.split = {}  # type: Dict[str, Offer]

    def _delete_past_offers(
        self, existing_offers: Dict[Offer, str], current_time_slot: DateTime
    ) -> Dict[Offer, str]:
        offers = {}
        for offer, market_id in existing_offers.items():
            market = self.strategy.get_market_from_id(market_id)
            if market is not None:
                if offer.time_slot and offer.time_slot <= current_time_slot:
                    continue
                offers[offer] = market_id
        return offers

    def delete_past_markets_offers(self, current_time_slot: DateTime) -> None:
        """Remove offers from past markets to decrease memory utilization"""
        self.posted = self._delete_past_offers(self.posted, current_time_slot)
        self.bought = self._delete_past_offers(self.bought, current_time_slot)
        self.split = {}

    @property
    def open(self) -> Dict[Offer, str]:
        """Return all open offers on all markets"""
        open_offers = {}
        for offer, market_id in self.posted.items():
            if market_id not in self.sold:
                self.sold[market_id] = []
            if offer not in self.sold[market_id]:
                open_offers[offer] = market_id
        return open_offers

    def bought_offer(self, offer: Offer, market_id: str) -> None:
        """Store bought offer"""
        self.bought[offer] = market_id

    def sold_offer(self, offer: Offer, market_id: str) -> None:
        """Store sold offer"""
        self.sold = append_or_create_key(self.sold, market_id, offer)

    def is_offer_posted(self, market_id: str, offer_id: str) -> bool:
        """Check if offer is posted on the market"""
        return offer_id in [
            offer.id for offer, _market in self.posted.items() if market_id == _market
        ]

    def _get_sold_offer_ids_in_market(self, market_id: str) -> List[str]:
        sold_offer_ids = []
        for sold_offer in self.sold.get(market_id, []):
            sold_offer_ids.append(sold_offer.id)
        return sold_offer_ids

    def open_in_market(self, market_id: str, time_slot: DateTime = None) -> List[Offer]:
        """Get all open offers in market"""
        open_offers = []
        sold_offer_ids = self._get_sold_offer_ids_in_market(market_id)
        for offer, _market_id in self.posted.items():
            if (
                offer.id not in sold_offer_ids
                and market_id == _market_id
                and (time_slot is None or offer.time_slot == time_slot)
            ):
                open_offers.append(offer)
        return open_offers

    def open_offer_energy(self, market_id: str, time_slot: DateTime = None) -> float:
        """Get sum of open offers' energy in market"""
        return sum(o.energy for o in self.open_in_market(market_id, time_slot))

    def posted_in_market(self, market_id: str, time_slot: DateTime = None) -> List[Offer]:
        """Get list of posted offers in market"""
        return [
            offer
            for offer, _market in self.posted.items()
            if market_id == _market and (time_slot is None or offer.time_slot == time_slot)
        ]

    def posted_offer_energy(self, market_id: str, time_slot: DateTime = None) -> float:
        """Get energy of all posted offers"""
        return sum(
            o.energy
            for o in self.posted_in_market(market_id, time_slot)
            if time_slot is None or o.time_slot == time_slot
        )

    def sold_offer_energy(self, market_id: str, time_slot: DateTime = None) -> float:
        """Get energy of all sold offers"""
        return sum(
            o.energy
            for o in self.sold_in_market(market_id)
            if time_slot is None or o.time_slot == time_slot
        )

    def sold_offer_price(self, market_id: str, time_slot: DateTime = None) -> float:
        """Get sum of all sold offers' price"""
        return sum(
            o.price
            for o in self.sold_in_market(market_id)
            if time_slot is None or o.time_slot == time_slot
        )

    def sold_in_market(self, market_id: str) -> List[Offer]:
        """Get list of sold offers in a market"""
        return self.sold[market_id] if market_id in self.sold else []

    # pylint: disable=too-many-arguments
    def can_offer_be_posted(
        self,
        offer_energy: float,
        offer_price: float,
        available_energy: float,
        market: "MarketBase",
        replace_existing: bool = False,
        time_slot: Optional[DateTime] = None,
    ) -> bool:
        """
        Check whether an offer with the specified parameters can be posted on the market
        Args:
            offer_energy: Energy of the offer, in kWh
            offer_price: Price of the offer, in cents
            available_energy: Available energy of the strategy for trading, in kWh
            market: Market that the offer will be posted to
            replace_existing: Set to True if the posted and unsold offers should be replaced
            time_slot: Desired timeslot that the offer needs to be posted. Useful for future
                       markets where one market handles multiple timeslots

        Returns: True if the offer can be posted, False otherwise

        """

        if replace_existing:
            # Do not consider previous open offers, since they would be replaced by the current one
            posted_offer_energy = 0.0
        else:
            posted_offer_energy = self.posted_offer_energy(market.id, time_slot)

        total_posted_energy = offer_energy + posted_offer_energy

        return (
            total_posted_energy - available_energy
        ) < FLOATING_POINT_TOLERANCE and offer_price >= 0.0

    def post(self, offer: Offer, market_id: str) -> None:
        """Add offer to the posted dict"""
        # If offer was split already, don't post one with the same uuid again
        if offer.id not in self.split:
            self.posted[offer] = market_id

    def remove_offer_from_cache_and_market(
        self, market: "OneSidedMarket", offer_id: str = None
    ) -> List[str]:
        """Delete offer from the market and remove it from the dicts"""
        if offer_id is None:
            to_delete_offers = self.open_in_market(market.id)
        else:
            to_delete_offers = [o for o, m in self.posted.items() if o.id == offer_id]
        deleted_offer_ids = []
        for offer in to_delete_offers:
            market.delete_offer(offer.id)
            self._remove(offer)
            deleted_offer_ids.append(offer.id)
        return deleted_offer_ids

    def _remove(self, offer: Offer) -> bool:
        market_id = self.posted.pop(offer)
        if not market_id:
            return False
        assert isinstance(market_id, str)
        if market_id in self.sold and offer in self.sold[market_id]:
            self.strategy.log.warning("Offer already sold, cannot remove it.")
            self.posted[offer] = market_id
            return False
        return True

    def replace(self, old_offer: Offer, new_offer: Offer, market_id: str):
        """Replace old offer with new in the posted dict"""
        if self._remove(old_offer):
            self.post(new_offer, market_id)

    def on_trade(self, market_id: str, trade: Trade) -> None:
        """Update contents of posted and sold dicts on the event of an offer being traded"""
        try:
            if trade.seller.name != self.strategy.owner.name:
                return
            offer = trade.match_details.get("offer")
            if not offer:
                return
            if offer.id in self.split and offer in self.posted:
                # remove from posted as it is traded already
                self._remove(self.split[offer.id])
            self.sold_offer(offer, market_id)
        except AttributeError as ex:
            raise SimulationException("Trade event before strategy was initialized.") from ex

    def on_offer_split(
        self, original_offer: Offer, accepted_offer: Offer, residual_offer: Offer, market_id: str
    ) -> None:
        """React to the event of an offer split"""
        if original_offer.seller.name == self.strategy.owner.name:
            self.split[original_offer.id] = accepted_offer
            self.post(residual_offer, market_id)
            if original_offer in self.posted:
                self.replace(original_offer, accepted_offer, market_id)


class BaseStrategy(EventMixin, AreaBehaviorBase, ABC):
    """
    Should be inherited by every strategy class. Keep track of the offers posted to the different
    markets, thus removing the need to access the market to view the offers that the strategy
    has posted. Define a common interface which all strategies should implement.
    """

    # pylint: disable=too-many-public-methods
    def __init__(self):
        super().__init__()
        self.offers = Offers(self)
        self.enabled = True
        self._allowed_disable_events = [AreaEvent.ACTIVATE, MarketEvent.OFFER_TRADED]
        self.event_responses = []
        self._market_adapter = market_strategy_connection_adapter_factory()
        self._settlement_market_strategy = self._create_settlement_market_strategy()
        self._future_market_strategy = self._create_future_market_strategy()

    def serialize(self):
        """Serialize strategy status."""
        return {}

    @property
    def simulation_config(self) -> SimulationConfig:
        """Return the SimulationConfiguration used by the current market area.

        NOTE: this configuration is currently unique and shared across all areas, but this might
        change in the future (each area could have its own configuration).
        """
        return self.area.config

    @classmethod
    def _create_settlement_market_strategy(cls):
        return SettlementMarketStrategyInterface()

    def _create_future_market_strategy(self):
        return FutureMarketStrategyInterface()

    def energy_traded(self, market_id: str, time_slot: DateTime = None) -> float:
        """Get the traded energy on the market"""
        return self.offers.sold_offer_energy(market_id, time_slot)

    def energy_traded_costs(self, market_id: str, time_slot: DateTime = None) -> float:
        """Get the traded energy cost on the market"""
        return self.offers.sold_offer_price(market_id, time_slot)

    @property
    def trades(self) -> _TradeLookerUpper:
        """Get trades that concern this strategy from the market"""
        return _TradeLookerUpper(self.owner.name)

    @property
    def _is_eligible_for_balancing_market(self) -> bool:
        """Check if strategy can participate in the balancing market"""
        return (
            self.owner.name in DeviceRegistry.REGISTRY
            and ConstSettings.BalancingSettings.ENABLE_BALANCING_MARKET
        )

    def _remove_existing_offers(self, market: "OneSidedMarket", time_slot: DateTime) -> None:
        """Remove all existing offers in the market with respect to time_slot."""
        for offer in self.get_posted_offers(market, time_slot):
            assert offer.seller.name == self.owner.name
            self.offers.remove_offer_from_cache_and_market(market, offer.id)

    def post_offer(self, market, replace_existing=True, **offer_kwargs) -> Offer:
        """Post the offer on the specified market.

        Args:
            market: The market in which the offer must be placed.
            replace_existing (bool): if True, delete all previous offers.
            offer_kwargs: the parameters that will be used to create the Offer object.
        """
        if replace_existing:
            # Remove all existing offers that are still open in the market
            self._remove_existing_offers(market, offer_kwargs.get("time_slot") or market.time_slot)

        if not offer_kwargs.get("seller") or not isinstance(
            offer_kwargs.get("seller"), TraderDetails
        ):
            offer_kwargs["seller"] = TraderDetails(
                self.owner.name, self.owner.uuid, self.owner.name, self.owner.uuid
            )
        if not offer_kwargs.get("time_slot"):
            offer_kwargs["time_slot"] = market.time_slot

        offer = self._market_adapter.offer(market, **offer_kwargs)
        self.offers.post(offer, market.id)

        return offer

    def post_first_offer(
        self, market: "OneSidedMarket", energy_kWh: float, initial_energy_rate: float
    ) -> Optional[Offer]:
        """Post first and only offer for the strategy. Will fail if another offer already
        exists."""
        if any(offer.seller.uuid == self.owner.uuid for offer in market.get_offers().values()):
            self.owner.log.debug(
                "There is already another offer posted on the market, therefore"
                " do not repost another first offer."
            )
            return None
        return self.post_offer(
            market,
            replace_existing=True,
            price=energy_kWh * initial_energy_rate,
            energy=energy_kWh,
        )

    def get_posted_offers(
        self, market: "OneSidedMarket", time_slot: Optional[DateTime] = None
    ) -> List[Offer]:
        """Get list of posted offers from a market"""
        return self.offers.posted_in_market(market.id, time_slot)

    def get_market_from_id(self, market_id: str) -> Optional[MarketBase]:
        """Retrieve a market object from the market_id."""
        # Look in spot and future markets first
        if not self.area:
            return None
        market = self.area.get_spot_or_future_market_by_id(market_id)
        if market is not None:
            return market
        # Then check settlement markets
        markets = [m for m in self.area.settlement_markets.values() if m.id == market_id]
        if not markets:
            return None
        return markets[0]

    def are_offers_posted(self, market_id: str) -> bool:
        """Checks if any offers have been posted in the market slot with the given ID."""
        return len(self.offers.posted_in_market(market_id)) > 0

    def accept_offer(
        self,
        market: "OneSidedMarket",
        offer: Offer,
        *,
        buyer: TraderDetails = None,
        energy: float = None,
        trade_bid_info: "TradeBidOfferInfo" = None,
    ):
        """
        Accept an offer on a market.
        Args:
            market: Market that contains the offer that will be accepted
            offer: Offer object that will be accepted
            buyer: Buyer of the offer
            energy: Selected energy from the offer
            trade_bid_info: Only populated for chain trades, contains pricing info about the
                            source seller and buyer of the chain trade

        Returns: Trade object

        """
        if buyer is None:
            buyer = self.owner.name
        if not isinstance(offer, Offer):
            offer = market.offers[offer]
        trade = self._market_adapter.accept_offer(
            AcceptOfferParameters(market, offer, buyer, energy, trade_bid_info)
        )

        self.offers.bought_offer(trade.match_details["offer"], market.id)
        return trade

    def delete_offer(self, market: "OneSidedMarket", offer: Offer) -> None:
        """
        Delete offer from the market
        Args:
            market: Market that should contain the offer
            offer: Offer that needs to be deleted

        Returns: None

        """
        self._market_adapter.delete_offer(market, offer)

    def event_listener(self, event_type: Union[AreaEvent, MarketEvent], **kwargs):
        """Dispatches the events received by the strategy to the respective methods."""
        if self.enabled or event_type in self._allowed_disable_events:
            super().event_listener(event_type, **kwargs)

    def event_offer_traded(self, *, market_id: str, trade: Trade) -> None:
        """
        React to offer trades. This method is triggered by the MarketEvent.OFFER_TRADED event.
        """
        self.offers.on_trade(market_id, trade)

    def event_offer_split(
        self,
        *,
        market_id: str,
        original_offer: Offer,
        accepted_offer: Offer,
        residual_offer: Offer,
    ) -> None:
        """React to the event of an offer split"""
        self.offers.on_offer_split(original_offer, accepted_offer, residual_offer, market_id)

    def event_market_cycle(self) -> None:
        """Default market cycle event. Deallocates memory by removing offers from past markets."""
        if not constants.RETAIN_PAST_MARKET_STRATEGIES_STATE:
            if self.area:
                self.offers.delete_past_markets_offers(self.area.spot_market.time_slot)
        self.event_responses = []

    def _assert_if_trade_offer_price_is_too_low(self, market_id: str, trade: Trade) -> None:
        if trade.is_offer_trade and trade.seller.name == self.owner.name:
            offer = [
                o for o in self.offers.sold[market_id] if o.id == trade.match_details["offer"].id
            ][0]
            assert trade.trade_rate >= offer.energy_rate - FLOATING_POINT_TOLERANCE

    # pylint: disable=too-many-arguments
    def can_offer_be_posted(
        self,
        offer_energy: float,
        offer_price: float,
        available_energy: float,
        market: "OneSidedMarket",
        time_slot: Optional[DateTime],
        replace_existing: bool = False,
    ) -> bool:
        """Check if an offer with the selected attributes can be posted"""
        return self.offers.can_offer_be_posted(
            offer_energy,
            offer_price,
            available_energy,
            market,
            time_slot=time_slot,
            replace_existing=replace_existing,
        )

    def can_settlement_offer_be_posted(
        self,
        offer_energy: float,
        offer_price: float,
        market: "OneSidedMarket",
        replace_existing: bool = False,
    ) -> bool:
        """
        Checks whether an offer can be posted to the settlement market
        :param offer_energy: Energy of the offer that we want to post
        :param offer_price: Price of the offer that we want to post
        :param market: Settlement market that we want the offer to be posted to
        :param replace_existing: Boolean argument that controls whether the offer should replace
                                 existing offers from the same asset
        :return: True in case the offer can be posted, False otherwise
        """
        if not self.state.can_post_settlement_offer(market.time_slot):
            return False
        unsettled_energy_kWh = self.state.get_unsettled_deviation_kWh(market.time_slot)
        return self.offers.can_offer_be_posted(
            offer_energy,
            offer_price,
            unsettled_energy_kWh,
            market,
            time_slot=market.time_slot,
            replace_existing=replace_existing,
        )

    @property
    def spot_market(self) -> "MarketBase":
        """Return the spot_market member of the area."""
        return self.area.spot_market

    @property
    def spot_market_time_slot(self) -> Optional[DateTime]:
        """Time slot of the current spot market"""
        if not self.spot_market:
            return None
        return self.spot_market.time_slot

    def update_offer_rates(
        self, market: "OneSidedMarket", updated_rate: float, time_slot: Optional[DateTime] = None
    ) -> None:
        """Update the total price of all offers in the specified market based on their new rate."""
        if market.id not in self.offers.open.values():
            return

        for offer in self.get_posted_offers(market, time_slot):
            updated_price = limit_float_precision(offer.energy * updated_rate)
            if abs(offer.price - updated_price) <= FLOATING_POINT_TOLERANCE:
                continue
            try:
                # Delete the old offer and create a new equivalent one with an updated price
                market.delete_offer(offer.id)
                new_offer = market.offer(
                    updated_price,
                    offer.energy,
                    TraderDetails(
                        self.owner.name,
                        self.owner.uuid,
                        offer.seller.origin,
                        offer.seller.origin_uuid,
                    ),
                    original_price=updated_price,
                    time_slot=offer.time_slot or market.time_slot or time_slot,
                )
                self.offers.replace(offer, new_offer, market.id)
            except MarketException:
                continue

    def event_activate_price(self):
        """Configure strategy price parameters during the activate event."""


class BidEnabledStrategy(BaseStrategy):
    """
    Base strategy for all areas / assets that are eligible to post bids and interact with a
    two sided market
    """

    def __init__(self):
        super().__init__()
        self._bids = {}
        self._traded_bids = {}

    def energy_traded(self, market_id: str, time_slot: Optional[DateTime] = None) -> float:
        # pylint: disable=fixme
        # TODO: Potential bug when used for the storage strategy. Does not really make sense to
        # accumulate the energy sold and energy bought in one float variable
        offer_energy = super().energy_traded(market_id, time_slot)
        return offer_energy + self._traded_bid_energy(market_id, time_slot)

    def energy_traded_costs(self, market_id: str, time_slot: Optional[DateTime] = None) -> float:
        # pylint: disable=fixme
        # TODO: Same as the energy_traded method, the storage strategy will increase its revenue
        # from sold offers, and decrease its revenue from sold bids, therefore addition of the 2
        # is not appropriate
        offer_costs = super().energy_traded_costs(market_id, time_slot)
        return offer_costs + self._traded_bid_costs(market_id, time_slot)

    def _remove_existing_bids(self, market: MarketBase, time_slot: DateTime) -> None:
        """Remove all existing bids in the market with respect to time_slot."""
        for bid in self.get_posted_bids(market, time_slot=time_slot):
            assert bid.buyer.name == self.owner.name
            self.remove_bid_from_pending(market.id, bid.id)

    # pylint: disable=too-many-arguments
    def post_bid(
        self,
        market: MarketBase,
        price: float,
        energy: float,
        replace_existing: bool = True,
        time_slot: Optional[DateTime] = None,
    ) -> Bid:
        """
        Post bid to a specified market.
        Args:
            market: Market that the bid will be posted to
            price: Price of the bid, in cents
            energy: Energy of the bid, in kWh
            replace_existing: Controls whether all existing bids from the same strategy should be
                              deleted or not
            time_slot: Time slot associated with the bid

        Returns: The bid posted to the market

        """
        self._assert_bid_can_be_posted_on_market(market.id)
        if replace_existing:
            self._remove_existing_bids(market, time_slot or market.time_slot)

        bid = market.bid(
            price,
            energy,
            TraderDetails(self.owner.name, self.owner.uuid, self.owner.name, self.owner.uuid),
            original_price=price,
            time_slot=time_slot or market.time_slot,
        )
        self.add_bid_to_posted(market.id, bid)
        return bid

    def update_bid_rates(
        self, market: "TwoSidedMarket", updated_rate: float, time_slot: Optional[DateTime] = None
    ) -> None:
        """Replace the rate of all bids in the market slot with the given updated rate."""
        for bid in self.get_posted_bids(market, time_slot):
            if abs(bid.energy_rate - updated_rate) <= FLOATING_POINT_TOLERANCE:
                continue
            assert bid.buyer.name == self.owner.name

            self.remove_bid_from_pending(market.id, bid.id)
            self.post_bid(
                market,
                bid.energy * updated_rate,
                bid.energy,
                replace_existing=False,
                time_slot=bid.time_slot,
            )

    # pylint: disable=too-many-arguments
    def can_bid_be_posted(
        self,
        bid_energy: float,
        bid_price: float,
        required_energy_kWh: float,
        market: "TwoSidedMarket",
        replace_existing: bool = False,
        time_slot: Optional[DateTime] = None,
    ) -> bool:
        """Check if a bid can be posted to the market"""

        if replace_existing:
            posted_bid_energy = 0.0
        else:
            posted_bid_energy = self.posted_bid_energy(market.id, time_slot)

        total_posted_energy = bid_energy + posted_bid_energy

        return total_posted_energy <= required_energy_kWh and bid_price >= 0.0

    def can_settlement_bid_be_posted(
        self,
        bid_energy: float,
        bid_price: float,
        market: "TwoSidedMarket",
        replace_existing: bool = False,
    ) -> bool:
        """
        Checks whether a bid can be posted to the settlement market
        :param bid_energy: Energy of the bid that we want to post
        :param bid_price: Price of the bid that we want to post
        :param market: Settlement market that we want the bid to be posted to
        :param replace_existing: Boolean argument that controls whether the bid should replace
                                 existing bids from the same asset
        :return: True in case the bid can be posted, False otherwise
        """
        if not self.state.can_post_settlement_bid(market.time_slot):
            return False
        unsettled_energy_kWh = self.state.get_unsettled_deviation_kWh(market.time_slot)
        return self.can_bid_be_posted(
            bid_energy,
            bid_price,
            unsettled_energy_kWh,
            market,
            time_slot=market.time_slot,
            replace_existing=replace_existing,
        )

    def is_bid_posted(self, market: "TwoSidedMarket", bid_id: str) -> bool:
        """Check if bid is posted to the market"""
        return bid_id in [bid.id for bid in self.get_posted_bids(market)]

    def posted_bid_energy(self, market_id: str, time_slot: Optional[DateTime] = None) -> float:
        """
        Calculate the energy of the already posted bids in the market
        Args:
            market_id: Id of the market
            time_slot: Useful for future markets, timeslot inside the market that the bid has been
                       posted to

        Returns: Total energy of all posted bids

        """
        if market_id not in self._bids:
            return 0.0
        return sum(
            b.energy
            for b in self._bids[market_id]
            if time_slot is None or b.time_slot == time_slot
        )

    def _traded_bid_energy(self, market_id: str, time_slot: Optional[DateTime] = None) -> float:
        return sum(
            b.energy
            for b in self._get_traded_bids_from_market(market_id)
            if time_slot is None or b.time_slot == time_slot
        )

    def _traded_bid_costs(self, market_id: str, time_slot: Optional[DateTime] = None) -> float:
        return sum(
            b.price
            for b in self._get_traded_bids_from_market(market_id)
            if time_slot is None or b.time_slot == time_slot
        )

    def remove_bid_from_pending(self, market_id: str, bid_id: str = None) -> List[str]:
        """Remove bid from pending bids dict"""
        self._assert_bid_can_be_posted_on_market(market_id)
        market = self.get_market_from_id(market_id)
        if market is None:
            return []
        if bid_id is None:
            deleted_bid_ids = [bid.id for bid in self.get_posted_bids(market)]
        else:
            deleted_bid_ids = [bid_id]
        for b_id in deleted_bid_ids:
            if b_id in market.bids.keys():
                market.delete_bid(b_id)
        self._bids[market.id] = [
            bid for bid in self.get_posted_bids(market) if bid.id not in deleted_bid_ids
        ]
        return deleted_bid_ids

    def add_bid_to_posted(self, market_id: str, bid: Bid) -> None:
        """Add bid to posted bids dict"""
        if market_id not in self._bids:
            self._bids[market_id] = []
        self._bids[market_id].append(bid)

    def add_bid_to_bought(self, bid: Bid, market_id: str, remove_bid: bool = True) -> None:
        """Add bid to traded bids dict"""
        if market_id not in self._traded_bids:
            self._traded_bids[market_id] = []
        self._traded_bids[market_id].append(bid)
        if remove_bid:
            self.remove_bid_from_pending(market_id, bid.id)

    def _get_traded_bids_from_market(self, market_id: str) -> List[Bid]:
        if market_id not in self._traded_bids:
            return []
        return self._traded_bids[market_id]

    def are_bids_posted(self, market_id: str, time_slot: DateTime = None) -> bool:
        """Checks if any bids have been posted in the market slot with the given ID."""
        if market_id not in self._bids:
            return False
        # time_slot is empty when called for spot markets, where we can retrieve the bids for a
        # time_slot only by the market_id. For the future markets, the time_slot needs to be
        # defined for the correct bid selection.
        return (
            len(
                [
                    bid
                    for bid in self._bids[market_id]
                    if time_slot is None or bid.time_slot == time_slot
                ]
            )
            > 0
        )

    def post_first_bid(
        self, market: "MarketBase", energy_Wh: float, initial_energy_rate: float
    ) -> Optional[Bid]:
        """Post first and only bid for the strategy. Will fail if another bid already exists."""
        # It will be safe to remove this check once we remove the event_market_cycle being
        # called twice, but still it is nice to have it here as a precaution. In general, there
        # should be only bid from a device to a market at all times, which will be replaced if
        # it needs to be updated. If this check is not there, the market cycle event will post
        # one bid twice, which actually happens on the very first market slot cycle.
        if any(bid.buyer.name == self.owner.name for bid in market.get_bids().values()):
            self.owner.log.debug(
                "There is already another bid posted on the market, therefore"
                " do not repost another first bid."
            )
            return None
        return self.post_bid(
            market,
            energy_Wh * initial_energy_rate / 1000.0,
            energy_Wh / 1000.0,
        )

    def get_posted_bids(
        self, market: "MarketBase", time_slot: Optional[DateTime] = None
    ) -> List[Bid]:
        """Get list of posted bids from a market"""
        if market.id not in self._bids:
            return []
        return [b for b in self._bids[market.id] if time_slot is None or b.time_slot == time_slot]

    def _assert_bid_can_be_posted_on_market(self, market_id):
        assert (
            ConstSettings.MASettings.MARKET_TYPE == SpotMarketTypeEnum.TWO_SIDED.value
            or self.area.is_market_future(market_id)
            or self.area.is_market_settlement(market_id)
        ), (
            "Invalid state, cannot receive a bid if single sided market is globally configured or "
            "if it is not a future or settlement market bid."
        )

    def event_bid_deleted(self, *, market_id: str, bid: Bid) -> None:
        self._assert_bid_can_be_posted_on_market(market_id)

        if bid.buyer.name != self.owner.name:
            return
        self.remove_bid_from_pending(market_id, bid.id)

    # pylint: disable=unused-argument
    def event_bid_split(
        self, *, market_id: str, original_bid: Bid, accepted_bid: Bid, residual_bid: Bid
    ) -> None:
        self._assert_bid_can_be_posted_on_market(market_id)

        if accepted_bid.buyer.name != self.owner.name:
            return
        self.add_bid_to_posted(market_id, bid=accepted_bid)
        self.add_bid_to_posted(market_id, bid=residual_bid)

    def event_bid_traded(self, *, market_id: str, bid_trade: Trade) -> None:
        """Register a successful bid when a trade is concluded for it.

        This method is triggered by the MarketEvent.BID_TRADED event.
        """
        self._assert_bid_can_be_posted_on_market(market_id)

        if bid_trade.buyer.name == self.owner.name:
            self.add_bid_to_bought(bid_trade.match_details["bid"], market_id)

    def _get_future_bids_from_list(self, bids: List) -> List:
        update_bids_list = []
        for bid in bids:
            if bid.time_slot > self.area.spot_market.time_slot:
                update_bids_list.append(bid)
        return update_bids_list

    def _delete_past_bids(self, existing_bids: Dict) -> Dict:
        updated_bids_dict = {}
        for market_id, bids in existing_bids.items():
            if market_id == self.area.future_markets.id:
                updated_bids_dict.update({market_id: self._get_future_bids_from_list(bids)})
        return updated_bids_dict

    def event_market_cycle(self) -> None:
        if not constants.RETAIN_PAST_MARKET_STRATEGIES_STATE:
            self._bids = self._delete_past_bids(self._bids)
            self._traded_bids = self._delete_past_bids(self._traded_bids)

        super().event_market_cycle()

    def assert_if_trade_bid_price_is_too_high(self, market: "MarketBase", trade: "Trade") -> None:
        """
        Assert whether the bid rate of the trade is less than the original bid rate. Useful
        for asserting that the clearing rate is lower than the rate that was posted originally on
        the bid.
        """
        if trade.is_bid_trade and trade.buyer.name == self.owner.name:
            bid = [
                bid
                for bid in self.get_posted_bids(market)
                if bid.id == trade.match_details["bid"].id
            ]
            if not bid:
                return
            assert trade.trade_rate <= bid[0].energy_rate + FLOATING_POINT_TOLERANCE
