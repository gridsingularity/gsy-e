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
from d3a.models.strategy.area_agents.inter_area_agent import InterAreaAgent
from d3a.models.strategy.area_agents.one_sided_engine import IAAEngine
from d3a.d3a_core.util import make_iaa_name
from d3a_interface.constants_limits import ConstSettings
from numpy.random import random


class OneSidedAgent(InterAreaAgent):
    def __init__(self, *, owner, higher_market, lower_market,
                 min_offer_age=ConstSettings.IAASettings.MIN_OFFER_AGE,
                 do_create_engine=True):
        super().__init__(owner=owner,
                         higher_market=higher_market,
                         lower_market=lower_market,
                         min_offer_age=min_offer_age)
        if do_create_engine:
            self.engines = [
                IAAEngine('High -> Low', higher_market, lower_market, min_offer_age, self),
                IAAEngine('Low -> High', lower_market, higher_market, min_offer_age, self),
            ]
        self.name = make_iaa_name(owner)

    def usable_offer(self, offer):
        """Prevent IAAEngines from trading their counterpart's offers"""
        return all(offer.id not in engine.forwarded_offers.keys() for engine in self.engines)

    def _get_market_from_market_id(self, market_id):
        if self.lower_market.id == market_id:
            return self.lower_market
        elif self.higher_market.id == market_id:
            return self.higher_market
        elif self.owner.get_future_market_from_id(market_id):
            return self.owner.get_future_market_from_id(market_id)
        elif self.owner.parent.get_future_market_from_id(market_id) is not None:
            return self.owner.parent.get_future_market_from_id(market_id)
        else:
            return None

    def event_tick(self):
        area = self.owner
        for engine in sorted(self.engines, key=lambda _: random()):
            engine.tick(area=area)

    def event_trade(self, *, market_id, trade):
        for engine in sorted(self.engines, key=lambda _: random()):
            engine.event_trade(trade=trade)

    def event_offer_deleted(self, *, market_id, offer):
        for engine in sorted(self.engines, key=lambda _: random()):
            engine.event_offer_deleted(offer=offer)

    def event_offer_split(self, *, market_id,  original_offer, accepted_offer, residual_offer):
        for engine in sorted(self.engines, key=lambda _: random()):
            engine.event_offer_split(market_id=market_id,
                                     original_offer=original_offer,
                                     accepted_offer=accepted_offer,
                                     residual_offer=residual_offer)

    def __repr__(self):
        return "<OneSidedAgent {s.name} {s.time_slot}>".format(s=self)
