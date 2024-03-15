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
from typing import Optional, TYPE_CHECKING

import random

from gsy_e.models.market import MarketBase
from gsy_e.models.strategy.market_agents.market_agent import MarketAgent
from gsy_e.models.strategy.market_agents.one_sided_engine import MAEngine

if TYPE_CHECKING:
    from gsy_framework.data_classes import Offer, Trade


class OneSidedAgent(MarketAgent):
    """Inter area agent implementation for the one-sided case."""

    def _create_engines(self):
        self.engines = [
            MAEngine("High -> Low", self.higher_market, self.lower_market,
                     self.min_offer_age, self),
            MAEngine("Low -> High", self.lower_market, self.higher_market,
                     self.min_offer_age, self),
        ]

    def usable_offer(self, offer: "Offer") -> bool:
        """Prevent MAEngines from trading their counterpart's offers"""
        return all(offer.id not in engine.forwarded_offers.keys() for engine in self.engines)

    def get_market_from_market_id(self, market_id: str) -> Optional[MarketBase]:
        """Return Market object from market_id."""
        if self.lower_market.id == market_id:
            return self.lower_market
        if self.higher_market.id == market_id:
            return self.higher_market
        if self.owner.get_spot_or_future_market_by_id(market_id):
            return self.owner.get_spot_or_future_market_by_id(market_id)
        if self.owner.parent.get_spot_or_future_market_by_id(market_id) is not None:
            return self.owner.parent.get_spot_or_future_market_by_id(market_id)

        return None

    def event_tick(self):
        area = self.owner
        for engine in random.sample(self.engines, len(self.engines)):
            engine.tick(area=area)

    # pylint: disable=unused-argument
    def event_offer(self, *, market_id: str, offer: "Offer"):
        for engine in sorted(self.engines, key=lambda _: random()):
            engine.event_offer(offer=offer)

    # pylint: disable=unused-argument
    def event_offer_traded(self, *, market_id: str, trade: "Trade"):
        for engine in random.sample(self.engines, len(self.engines)):
            engine.event_offer_traded(trade=trade)

    # pylint: disable=unused-argument
    def event_offer_deleted(self, *, market_id: str, offer: "Offer"):
        for engine in random.sample(self.engines, len(self.engines)):
            engine.event_offer_deleted(offer=offer)

    def event_offer_split(self, *, market_id: str,  original_offer: "Offer",
                          accepted_offer: "Offer", residual_offer: "Offer"):
        for engine in random.sample(self.engines, len(self.engines)):
            engine.event_offer_split(market_id=market_id,
                                     original_offer=original_offer,
                                     accepted_offer=accepted_offer,
                                     residual_offer=residual_offer)

    def delete_engines(self) -> None:
        """Deletes all engine buffers, theirs contents and the engines themselves."""
        for engine in self.engines:
            del engine.forwarded_offers
            del engine.offer_age
            del engine.trade_residual
            del engine

    def __repr__(self) -> str:
        return f"<OneSidedAgent {self.name} {self.time_slot_str}>"
