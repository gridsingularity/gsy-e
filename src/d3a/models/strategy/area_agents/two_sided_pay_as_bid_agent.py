from d3a.models.strategy.area_agents.one_sided_agent import OneSidedAgent
from d3a.models.strategy.area_agents.two_sided_pay_as_bid_engine import TwoSidedPayAsBidEngine


class TwoSidedPayAsBidAgent(OneSidedAgent):

    def __init__(self, *, owner, higher_market, lower_market,
                 transfer_fee_pct=1, min_offer_age=1, balancing_agent=False):
        super().__init__(engine_type=TwoSidedPayAsBidEngine, owner=owner,
                         higher_market=higher_market, lower_market=lower_market,
                         transfer_fee_pct=transfer_fee_pct, min_offer_age=min_offer_age,
                         balancing_agent=balancing_agent)

    def usable_bid(self, bid):
        """Prevent IAAEngines from trading their counterpart's bids"""
        return all(bid.id not in engine.forwarded_bids.keys() for engine in self.engines)

    def event_bid_traded(self, *, market_id, bid_trade):
        for engine in self.engines:
            engine.event_bid_traded(bid_trade=bid_trade)

    def event_bid_deleted(self, *, market_id, bid):
        for engine in self.engines:
            engine.event_bid_deleted(bid=bid)
