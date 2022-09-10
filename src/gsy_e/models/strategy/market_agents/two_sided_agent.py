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
from typing import TYPE_CHECKING
from gsy_framework.constants_limits import ConstSettings
import random

from gsy_e.models.strategy.market_agents.one_sided_agent import OneSidedAgent
from gsy_e.models.strategy.market_agents.two_sided_engine import TwoSidedEngine

if TYPE_CHECKING:
    from gsy_framework.data_classes import Bid, Trade
    from gsy_e.models.area import Area
    from gsy_e.models.market import MarketBase


class TwoSidedAgent(OneSidedAgent):
    """Handles order forwarding between two-sided markets."""

    def __init__(self, *, owner: "Area", higher_market: "MarketBase", lower_market: "MarketBase",
                 min_offer_age: int = ConstSettings.MASettings.MIN_OFFER_AGE,
                 min_bid_age: int = ConstSettings.MASettings.MIN_BID_AGE):

        self.min_bid_age = min_bid_age
        super().__init__(owner=owner,
                         higher_market=higher_market,
                         lower_market=lower_market,
                         min_offer_age=min_offer_age)

    def _create_engines(self):
        self.engines = [
            TwoSidedEngine("High -> Low", self.higher_market, self.lower_market,
                           self.min_offer_age,
                           self.min_bid_age, self),
            TwoSidedEngine("Low -> High", self.lower_market, self.higher_market,
                           self.min_offer_age,
                           self.min_bid_age, self),
        ]

    def usable_bid(self, bid: "Bid") -> bool:
        """Prevent MAEngines from trading their counterpart's bids."""
        return all(bid.id not in engine.forwarded_bids.keys() for engine in self.engines)

    # pylint: disable=unused-argument
    def event_bid(self, *, market_id: str, bid: "Bid"):
        for engine in sorted(self.engines, key=lambda _: random()):
            engine.event_bid(bid)

    # pylint: disable=unused-argument
    def event_bid_traded(self, *, market_id: str, bid_trade: "Trade"):
        for engine in random.sample(self.engines, len(self.engines)):
            engine.event_bid_traded(bid_trade=bid_trade)

    # pylint: disable=unused-argument
    def event_bid_deleted(self, *, market_id: str, bid: "Bid"):
        for engine in random.sample(self.engines, len(self.engines)):
            engine.event_bid_deleted(bid=bid)

    def event_bid_split(self, *, market_id: str, original_bid: "Bid",
                        accepted_bid: "Bid", residual_bid: "Bid"):
        for engine in random.sample(self.engines, len(self.engines)):
            engine.event_bid_split(market_id=market_id,
                                   original_bid=original_bid,
                                   accepted_bid=accepted_bid,
                                   residual_bid=residual_bid)

    def delete_engines(self) -> None:
        """Deletes all engine buffers, theirs contents and the engines themselves."""
        super().delete_engines()
        for engine in self.engines:
            del engine.forwarded_bids
            del engine.bid_age
            del engine.bid_trade_residual
            del engine

    def __repr__(self) -> str:
        return f"<TwoSidedPayAsBidAgent {self.name} {self.time_slot_str}>"
