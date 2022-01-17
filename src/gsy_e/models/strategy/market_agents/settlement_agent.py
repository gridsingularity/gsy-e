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
from gsy_framework.constants_limits import ConstSettings

from gsy_e.models.strategy.market_agents.two_sided_agent import TwoSidedAgent
from gsy_e.models.strategy.market_agents.two_sided_engine import TwoSidedEngine


class SettlementAgent(TwoSidedAgent):
    """
    Extends TwoSidedAgent class to support settlement agents, in order to be able to
    forward bids and offers from one settlement market to another.
    """
    def __init__(self, owner, higher_market, lower_market,
                 min_offer_age=ConstSettings.MASettings.MIN_OFFER_AGE,
                 min_bid_age=ConstSettings.MASettings.MIN_BID_AGE):

        super().__init__(owner=owner,
                         higher_market=higher_market,
                         lower_market=lower_market,
                         min_offer_age=min_offer_age,
                         min_bid_age=min_bid_age)
        self.name = self.owner.name

    def _create_engines(self):
        self.engines = [
            TwoSidedEngine('High -> Low', self.higher_market, self.lower_market,
                           self.min_offer_age, self.min_bid_age, self),
            TwoSidedEngine('Low -> High', self.lower_market, self.higher_market,
                           self.min_offer_age, self.min_bid_age, self),
        ]
