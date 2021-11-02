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
from d3a.gsy_e_core.exceptions import MarketException
from d3a.models.strategy.pv import PVStrategy
from d3a.models.strategy import INF_ENERGY
from gsy_framework.constants_limits import ConstSettings


class OneSidedAlternativePricingAgent(OneSidedAgent):

    # The following is an artificial number but has to be >= 2:
    MIN_SLOT_AGE = 2

    def __init__(self, *, owner, higher_market, lower_market,
                 min_offer_age=ConstSettings.IAASettings.MIN_OFFER_AGE):
        super().__init__(owner=owner,
                         higher_market=higher_market, lower_market=lower_market,
                         min_offer_age=min_offer_age)

    @staticmethod
    def _get_children_by_name(area, name):
        return next((c for c in area.children if c.name == name), None)

    def _buy_energy_alternative_pricing_schemes(self, area):
        if not all(child.children == [] for child in self.owner.children):
            return
        try:
            for offer in self.lower_market.sorted_offers:
                if offer.seller == self.name:
                    continue
                seller = self._get_children_by_name(area, offer.seller)
                if seller is not None and isinstance(seller.strategy, PVStrategy):
                    if ConstSettings.IAASettings.AlternativePricing.PRICING_SCHEME == 1:
                        sell_rate = 0
                    elif ConstSettings.IAASettings.AlternativePricing.PRICING_SCHEME == 2:
                        sell_rate = \
                            area.config.market_maker_rate[self.lower_market.time_slot] * \
                            ConstSettings.IAASettings.AlternativePricing.FEED_IN_TARIFF_PERCENTAGE\
                            / 100
                    elif ConstSettings.IAASettings.AlternativePricing.PRICING_SCHEME == 3:
                        sell_rate = area.config.market_maker_rate[self.lower_market.time_slot]
                    else:
                        raise MarketException
                    offer.update_price(offer.energy * sell_rate)
                    self.accept_offer(self.lower_market, offer)

        except MarketException:
            self.log.exception("Alternative pricing scheme: "
                               "An Error occurred while buying an offer")

    def event_tick(self):
        area = self.owner
        if area.current_tick_in_slot >= self.MIN_SLOT_AGE and \
                ConstSettings.IAASettings.AlternativePricing.PRICING_SCHEME != 0:
            self._buy_energy_alternative_pricing_schemes(area)

    def event_market_cycle(self):
        if ConstSettings.IAASettings.AlternativePricing.PRICING_SCHEME != 0:
            energy_per_slot = INF_ENERGY
            energy_rate = self.owner.config.market_maker_rate[self.lower_market.time_slot]

            self.lower_market.offer(
                energy_per_slot * energy_rate,
                energy_per_slot,
                ConstSettings.IAASettings.AlternativePricing.ALT_PRICING_MARKET_MAKER_NAME,
                ConstSettings.IAASettings.AlternativePricing.ALT_PRICING_MARKET_MAKER_NAME,
                original_price=energy_per_slot * energy_rate
            )
