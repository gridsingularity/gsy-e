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

from gsy_e.models.strategy.market_agents.future_engine import FutureEngine
from gsy_e.models.strategy.market_agents.two_sided_agent import TwoSidedAgent

if TYPE_CHECKING:
    from gsy_e.models.area import Area
    from gsy_e.models.market.future import FutureMarkets


class FutureAgent(TwoSidedAgent):
    """Handler for MAEngines for the future markets."""

    def __init__(self, *, owner: "Area", higher_market: "FutureMarkets",
                 lower_market: "FutureMarkets",
                 min_offer_age: int = ConstSettings.MASettings.MIN_OFFER_AGE,
                 min_bid_age: int = ConstSettings.MASettings.MIN_BID_AGE):

        super().__init__(owner=owner,
                         higher_market=higher_market,
                         lower_market=lower_market,
                         min_offer_age=min_offer_age,
                         min_bid_age=min_bid_age)
        self.name = self.owner.name

    def _create_engines(self):
        self.engines = [
            FutureEngine("High -> Low", self.higher_market, self.lower_market,
                         self.min_offer_age, self.min_bid_age, self),
            FutureEngine("Low -> High", self.lower_market, self.higher_market,
                         self.min_offer_age, self.min_bid_age, self),
        ]

    def delete_engines(self) -> None:
        """Delete all bids and offers for the non-future markets (overwriting super() method)."""
        if not self.owner.current_market:
            return
        for engine in self.engines:
            engine.clean_up_order_buffers(self.owner.current_market.time_slot)
