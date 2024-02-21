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
from gsy_framework.data_classes import TraderDetails
from numpy.random import random

from gsy_e.constants import FLOATING_POINT_TOLERANCE
from gsy_e.models.strategy.market_agents.one_sided_agent import OneSidedAgent
from gsy_e.models.strategy.market_agents.one_sided_engine import BalancingEngine


class BalancingAgent(OneSidedAgent):
    """Market agent for balancing market"""

    def __init__(self, owner, higher_market, lower_market,
                 min_offer_age=ConstSettings.MASettings.MIN_OFFER_AGE):
        self.balancing_spot_trade_ratio = owner.balancing_spot_trade_ratio

        super().__init__(owner=owner,
                         higher_market=higher_market,
                         lower_market=lower_market,
                         min_offer_age=min_offer_age)
        self.name = self.owner.name

    def _create_engines(self):
        self.engines = [
            BalancingEngine("High -> Low", self.higher_market, self.lower_market,
                            self.min_offer_age, self),
            BalancingEngine("Low -> High", self.lower_market, self.higher_market,
                            self.min_offer_age, self),
        ]

    def __repr__(self):
        return f"<BalancingAgent {self.name} {self.time_slot_str}>"

    def event_tick(self):
        super().event_tick()
        if self.lower_market.unmatched_energy_downward > 0.0 or \
                self.lower_market.unmatched_energy_upward > 0.0:
            self._trigger_balancing_trades(self.lower_market.unmatched_energy_upward,
                                           self.lower_market.unmatched_energy_downward)

    def event_offer_traded(self, *, market_id, trade):
        market = self.get_market_from_market_id(market_id)
        if market is None:
            return

        self._calculate_and_buy_balancing_energy(market, trade)
        super().event_offer_traded(market_id=market_id, trade=trade)

    def event_bid_traded(self, *, market_id, bid_trade):
        if bid_trade.match_details.get("offer"):
            return

        market = self.get_market_from_market_id(market_id)
        if market is None:
            return

        self._calculate_and_buy_balancing_energy(market, bid_trade)
        super().event_bid_traded(market_id=market_id, bid_trade=bid_trade)

    def _calculate_and_buy_balancing_energy(self, market, trade):
        if trade.buyer.name != self.owner.name or \
                market.time_slot != self.lower_market.time_slot:
            return
        positive_balancing_energy = \
            trade.traded_energy * self.balancing_spot_trade_ratio + \
            self.lower_market.unmatched_energy_upward
        negative_balancing_energy = \
            trade.traded_energy * self.balancing_spot_trade_ratio + \
            self.lower_market.unmatched_energy_downward

        self._trigger_balancing_trades(positive_balancing_energy, negative_balancing_energy)

    def _trigger_balancing_trades(self, positive_balancing_energy, negative_balancing_energy):
        for offer in self.lower_market.sorted_offers:
            if offer.energy > FLOATING_POINT_TOLERANCE and \
                    positive_balancing_energy > FLOATING_POINT_TOLERANCE:
                balance_trade = self._balancing_trade(offer,
                                                      positive_balancing_energy)
                if balance_trade is not None:
                    positive_balancing_energy -= abs(balance_trade.traded_energy)
            elif offer.energy < FLOATING_POINT_TOLERANCE < negative_balancing_energy:
                balance_trade = self._balancing_trade(offer,
                                                      -negative_balancing_energy)
                if balance_trade is not None:
                    negative_balancing_energy -= abs(balance_trade.traded_energy)

        self.lower_market.unmatched_energy_upward = positive_balancing_energy
        self.lower_market.unmatched_energy_downward = negative_balancing_energy

    def _balancing_trade(self, offer, target_energy):
        trade = None
        buyer = TraderDetails(
            (self.owner.name
             if self.owner.name != offer.seller.name
             else f"{self.owner.name} Reserve"),
            self.owner.uuid)

        if abs(offer.energy) <= abs(target_energy):
            trade = self.lower_market.accept_offer(offer_or_id=offer,
                                                   buyer=buyer,
                                                   energy=offer.energy)
        elif abs(offer.energy) >= abs(target_energy):
            trade = self.lower_market.accept_offer(offer_or_id=offer,
                                                   buyer=buyer,
                                                   energy=target_energy)
        return trade

    def event_balancing_trade(self, *, market_id, trade, offer=None):
        for engine in sorted(self.engines, key=lambda _: random()):
            engine.event_offer_traded(trade=trade)

    def event_balancing_offer_split(self, *, market_id, original_offer, accepted_offer,
                                    residual_offer):
        for engine in sorted(self.engines, key=lambda _: random()):
            engine.event_offer_split(market_id=market_id,
                                     original_offer=original_offer,
                                     accepted_offer=accepted_offer,
                                     residual_offer=residual_offer)
