from d3a_interface.constants_limits import ConstSettings

from d3a.gsy_core.util import make_sa_name
from d3a.models.strategy.area_agents.two_sided_agent import TwoSidedAgent
from d3a.models.strategy.area_agents.two_sided_engine import TwoSidedEngine


class SettlementAgent(TwoSidedAgent):
    """
    Extends TwoSidedAgent class to support settlement agents, in order to be able to
    forward bids and offers from one settlement market to another.
    """
    def __init__(self, owner, higher_market, lower_market,
                 min_offer_age=ConstSettings.IAASettings.MIN_OFFER_AGE,
                 min_bid_age=ConstSettings.IAASettings.MIN_BID_AGE):
        self.engines = [
            TwoSidedEngine('High -> Low', higher_market, lower_market,
                           min_offer_age, min_bid_age, self),
            TwoSidedEngine('Low -> High', lower_market, higher_market,
                           min_offer_age, min_bid_age, self),
        ]
        super().__init__(owner=owner, higher_market=higher_market,
                         lower_market=lower_market,
                         min_offer_age=min_offer_age, min_bid_age=min_bid_age)
        self.name = make_sa_name(self.owner)
