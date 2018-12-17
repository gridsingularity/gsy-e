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
from d3a.models.strategy.area_agents.two_sided_pay_as_bid_agent import TwoSidedPayAsBidAgent
from d3a.models.strategy.area_agents.two_sided_pay_as_clear_engine import TwoSidedPayAsClearEngine


class TwoSidedPayAsClearAgent(TwoSidedPayAsBidAgent):

    def __init__(self, *, owner, higher_market, lower_market,
                 transfer_fee_pct=1, min_offer_age=1):
        super().__init__(owner=owner,
                         higher_market=higher_market, lower_market=lower_market,
                         transfer_fee_pct=transfer_fee_pct, min_offer_age=min_offer_age,
                         engine_type=TwoSidedPayAsClearEngine)

    def __repr__(self):
        return "<TwoSidedPayAsClearAgent {s.name} {s.time_slot}>".format(s=self)
