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
import sys

from d3a.models.strategy.commercial_producer import CommercialStrategy
from d3a.models.strategy import BidEnabledStrategy
from d3a.d3a_core.exceptions import MarketException
from d3a_interface.constants_limits import ConstSettings
from d3a.models.read_user_profile import read_arbitrary_profile, InputProfileTypes

INF_ENERGY = int(sys.maxsize)


class InfiniteBusStrategy(CommercialStrategy, BidEnabledStrategy):
    parameters = ('energy_sell_rate', 'energy_buy_rate')

    def __init__(self, energy_sell_rate=None, energy_buy_rate=None):
        super().__init__()
        self.energy_per_slot_kWh = INF_ENERGY
        self.energy_buy_rate = energy_buy_rate
        self.energy_rate = energy_sell_rate

    def event_activate(self):
        self.energy_rate = self.area.config.market_maker_rate if self.energy_rate is None \
            else read_arbitrary_profile(InputProfileTypes.IDENTITY, self.energy_rate)

        self.energy_buy_rate = self.area.config.market_maker_rate if self.energy_buy_rate is None \
            else read_arbitrary_profile(InputProfileTypes.IDENTITY, self.energy_buy_rate)

    def buy_energy(self, market):
        for offer in market.sorted_offers:
            if offer.seller == self.owner.name:
                # Don't buy our own offer
                continue
            if (offer.price / offer.energy) <= self.energy_buy_rate[market.time_slot]:
                try:
                    self.accept_offer(market, offer, buyer_origin=self.owner.name)
                except MarketException:
                    # Offer already gone etc., try next one.
                    continue

    def event_tick(self):
        if ConstSettings.IAASettings.MARKET_TYPE == 1:
            for market in self.area.all_markets:
                self.buy_energy(market)

    def event_market_cycle(self):
        super().event_market_cycle()
        if ConstSettings.IAASettings.MARKET_TYPE == 2 or \
           ConstSettings.IAASettings.MARKET_TYPE == 3:
            for market in self.area.all_markets:
                self.post_bid(market,
                              self.energy_buy_rate[market.time_slot] * INF_ENERGY, INF_ENERGY,
                              buyer_origin=self.owner.name)
