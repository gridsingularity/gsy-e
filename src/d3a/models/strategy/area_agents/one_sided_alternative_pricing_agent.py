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
from d3a.models.strategy.area_agents.one_sided_agent import OneSidedAgent
from d3a.models.strategy.area_agents.one_sided_engine import IAAEngine
from d3a.d3a_core.exceptions import MarketException
from d3a.d3a_core.sim_results.area_statistics import _is_house_node
from d3a.models.strategy.pv import PVStrategy
from d3a.models.const import ConstSettings


class OneSidedAlternativePricingAgent(OneSidedAgent):
    def __init__(self, *, owner, higher_market, lower_market, min_offer_age=1,
                 engine_type=IAAEngine):
        super().__init__(engine_type=engine_type, owner=owner, higher_market=higher_market,
                         lower_market=lower_market, transfer_fee_pct=0,
                         min_offer_age=min_offer_age)

    @staticmethod
    def _get_children_by_name(area, name):
        for child in area.children:
            if child.name == name:
                return child
        return None

    def _buy_energy_alternative_pricing_schemes(self, area):
        if _is_house_node(self.owner):
            try:
                for offer in self.lower_market.sorted_offers:
                    if offer.seller != self.name:
                        seller = self._get_children_by_name(area, offer.seller)
                        if seller is not None and isinstance(seller.strategy, PVStrategy):
                            if ConstSettings.IAASettings.PRICING_SCHEME == 1:
                                sell_rate = 0
                            elif ConstSettings.IAASettings.PRICING_SCHEME == 2:
                                sell_rate = \
                                    ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE * \
                                    ConstSettings.IAASettings.FEED_IN_TARIFF_PERCENTAGE / 100
                            elif ConstSettings.IAASettings.PRICING_SCHEME == 3:
                                sell_rate = ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE
                            else:
                                raise MarketException
                            offer.price = offer.energy * sell_rate
                            self.accept_offer(offer.market, offer)

            except MarketException:
                self.log.exception("Alternative pricing scheme: "
                                   "An Error occurred while buying an offer")

    def event_tick(self, *, area):

        # The following is an artificial number but has to be >= 2:
        min_slot_age = 2
        if area.current_tick_in_slot - min_slot_age >= 0 and \
                ConstSettings.IAASettings.PRICING_SCHEME != 0:
            self._buy_energy_alternative_pricing_schemes(area)

        super().event_tick(area=area)
