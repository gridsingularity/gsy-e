from d3a.models.strategy.area_agents.inter_area_agent import InterAreaAgent
from d3a.models.strategy.area_agents.one_sided_engine import IAAEngine
from d3a.d3a_core.util import make_iaa_name


class OneSidedAgent(InterAreaAgent):
    def __init__(self, *, owner, higher_market, lower_market,
                 transfer_fee_pct=1, min_offer_age=1, engine_type=IAAEngine):
        super().__init__(engine_type=engine_type, owner=owner, higher_market=higher_market,
                         lower_market=lower_market, transfer_fee_pct=transfer_fee_pct,
                         min_offer_age=min_offer_age)
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

    def event_tick(self, *, area):
        if area != self.owner:
            # We're connected to both areas but only want tick events from our owner
            return

        for engine in self.engines:
            engine.tick(area=area)

    def event_trade(self, *, market_id, trade):
        for engine in self.engines:
            engine.event_trade(trade=trade)

    def event_offer_deleted(self, *, market_id, offer):
        for engine in self.engines:
            engine.event_offer_deleted(offer=offer)

    def event_offer_changed(self, *, market_id, existing_offer, new_offer):
        for engine in self.engines:
            engine.event_offer_changed(market_id=market_id,
                                       existing_offer=existing_offer,
                                       new_offer=new_offer)
