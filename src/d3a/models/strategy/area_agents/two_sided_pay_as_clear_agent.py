from d3a.models.strategy.area_agents.two_sided_pay_as_bid_agent import TwoSidedPayAsBidAgent
from d3a.models.strategy.area_agents.two_sided_pay_as_clear_engine import TwoSidedPayAsClearEngine


class TwoSidedPayAsClearAgent(TwoSidedPayAsBidAgent):

    def __init__(self, *, owner, higher_market, lower_market,
                 transfer_fee_pct=1, min_offer_age=1):
        super().__init__(owner=owner,
                         higher_market=higher_market, lower_market=lower_market,
                         transfer_fee_pct=transfer_fee_pct, min_offer_age=min_offer_age,
                         engine_type=TwoSidedPayAsClearEngine)
