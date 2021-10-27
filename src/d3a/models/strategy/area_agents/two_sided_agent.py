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
from numpy.random import random
from d3a.models.strategy.area_agents.one_sided_agent import OneSidedAgent
from d3a.models.strategy.area_agents.two_sided_engine import TwoSidedEngine
from gsy_framework.constants_limits import ConstSettings


class TwoSidedAgent(OneSidedAgent):

    def __init__(self, *, owner, higher_market, lower_market,
                 min_offer_age=ConstSettings.IAASettings.MIN_OFFER_AGE,
                 min_bid_age=ConstSettings.IAASettings.MIN_BID_AGE):
        self.engines = [
            TwoSidedEngine('High -> Low', higher_market, lower_market, min_offer_age,
                           min_bid_age, self),
            TwoSidedEngine('Low -> High', lower_market, higher_market, min_offer_age,
                           min_bid_age, self),
        ]
        super().__init__(owner=owner,
                         higher_market=higher_market, lower_market=lower_market,
                         min_offer_age=min_offer_age, do_create_engine=False)

    def usable_bid(self, bid):
        """Prevent IAAEngines from trading their counterpart's bids"""
        return all(bid.id not in engine.forwarded_bids.keys() for engine in self.engines)

    def event_bid_traded(self, *, market_id, bid_trade):
        for engine in sorted(self.engines, key=lambda _: random()):
            engine.event_bid_traded(bid_trade=bid_trade)

    def event_bid_deleted(self, *, market_id, bid):
        for engine in sorted(self.engines, key=lambda _: random()):
            engine.event_bid_deleted(bid=bid)

    def event_bid_split(self, *, market_id, original_bid, accepted_bid, residual_bid):
        for engine in sorted(self.engines, key=lambda _: random()):
            engine.event_bid_split(market_id=market_id,
                                   original_bid=original_bid,
                                   accepted_bid=accepted_bid,
                                   residual_bid=residual_bid)

    def __repr__(self):
        return "<TwoSidedPayAsBidAgent {s.name} {s.time_slot}>".format(s=self)
