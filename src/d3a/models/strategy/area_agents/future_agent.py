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
from typing import TYPE_CHECKING

from d3a_interface.constants_limits import ConstSettings

from d3a.d3a_core.util import make_sa_name
from d3a.models.market.future import FutureMarkets
from d3a.models.strategy.area_agents.future_engine import FutureEngine
from d3a.models.strategy.area_agents.two_sided_agent import TwoSidedAgent

if TYPE_CHECKING:
    from d3a.models.area import Area


class FutureAgent(TwoSidedAgent):
    """Handler for IAAEngines for the future markets."""

    def __init__(self, *, owner: "Area", higher_market: FutureMarkets,
                 lower_market: FutureMarkets,
                 min_offer_age: int = ConstSettings.IAASettings.MIN_OFFER_AGE,
                 min_bid_age: int = ConstSettings.IAASettings.MIN_BID_AGE):

        super().__init__(owner=owner, higher_market=higher_market,
                         lower_market=lower_market,
                         min_offer_age=min_offer_age, min_bid_age=min_bid_age,
                         do_create_engine=False)
        self.engines = [
            FutureEngine("High -> Low", higher_market, lower_market,
                         min_offer_age, min_bid_age, self),
            FutureEngine("Low -> High", lower_market, higher_market,
                         min_offer_age, min_bid_age, self),
        ]
        self.name = make_sa_name(self.owner)

    def _clean_up_engine_buffers(self) -> None:
        if not self.owner.current_market:
            return
        for engine in self.engines:
            engine.clean_up_order_buffers(self.owner.current_market.time_slot)

    def delete_engines(self) -> None:
        """Delete all bids and offers for the non-future markets (overwriting super() method)."""
        self._clean_up_engine_buffers()

    def event_market_cycle(self):
        super().event_market_cycle()
        self.delete_engines()
