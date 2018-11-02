from d3a.util import make_ba_name, make_iaa_name
from d3a.models.strategy.area_agents.one_sided_agent import OneSidedAgent


class BalancingAgent(OneSidedAgent):
    def __init__(self, owner, higher_market, lower_market,
                 transfer_fee_pct=1, min_offer_age=1):
        self.balancing_spot_trade_ratio = owner.balancing_spot_trade_ratio
        super().__init__(owner=owner, higher_market=higher_market,
                         lower_market=lower_market, transfer_fee_pct=transfer_fee_pct,
                         min_offer_age=min_offer_age)
        self.name = make_ba_name(self.owner)

    def event_tick(self, *, area):
        super().event_tick(area=area)
        if self.lower_market.unmatched_energy_downward > 0.0 or \
                self.lower_market.unmatched_energy_upward > 0.0:
            self._trigger_balancing_trades(self.lower_market.unmatched_energy_upward,
                                           self.lower_market.unmatched_energy_downward)

    def event_trade(self, *, market_id, trade):
        market = self._get_market_from_market_id(market_id)
        if market is None:
            return

        self._calculate_and_buy_balancing_energy(market, trade)
        super().event_trade(market_id=market_id, trade=trade)

    def event_bid_traded(self, *, market_id, bid_trade):
        if bid_trade.already_tracked:
            return

        market = self._get_market_from_market_id(market_id)
        if market is None:
            return

        self._calculate_and_buy_balancing_energy(market, bid_trade)
        super().event_bid_traded(market_id=market_id, bid_trade=bid_trade)

    def _calculate_and_buy_balancing_energy(self, market, trade):
        if trade.buyer != make_iaa_name(self.owner) or \
                market.time_slot != self.lower_market.time_slot:
            return
        positive_balancing_energy = \
            trade.offer.energy * self.balancing_spot_trade_ratio + \
            self.lower_market.unmatched_energy_upward
        negative_balancing_energy = \
            trade.offer.energy * self.balancing_spot_trade_ratio + \
            self.lower_market.unmatched_energy_downward

        self._trigger_balancing_trades(positive_balancing_energy, negative_balancing_energy)

    def _trigger_balancing_trades(self, positive_balancing_energy, negative_balancing_energy):
        for offer in self.lower_market.sorted_offers:
            if offer.energy > 0 and positive_balancing_energy > 0:
                balance_trade = self._balancing_trade(offer,
                                                      positive_balancing_energy)
                if balance_trade is not None:
                    positive_balancing_energy -= abs(balance_trade.offer.energy)
            elif offer.energy < 0 and negative_balancing_energy > 0:
                balance_trade = self._balancing_trade(offer,
                                                      -negative_balancing_energy)
                if balance_trade is not None:
                    negative_balancing_energy -= abs(balance_trade.offer.energy)

        self.lower_market.unmatched_energy_upward = positive_balancing_energy
        self.lower_market.unmatched_energy_downward = negative_balancing_energy

    def _balancing_trade(self, offer, target_energy):
        trade = None
        buyer = make_ba_name(self.owner) \
            if make_ba_name(self.owner) != offer.seller \
            else f"{self.owner.name} Reserve"
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
        for engine in self.engines:
            engine.event_trade(trade=trade)

    def event_balancing_offer_changed(self, *, market_id, existing_offer, new_offer):
        for engine in self.engines:
            engine.event_offer_changed(market_id=market_id,
                                       existing_offer=existing_offer,
                                       new_offer=new_offer)
