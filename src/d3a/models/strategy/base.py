from collections import defaultdict
from logging import getLogger
from typing import Dict, List

from d3a.models.base import AreaBehaviorBase
from d3a.models.events import EventMixin
from d3a.models.market import Market, Trade


log = getLogger(__name__)


class BaseStrategy(EventMixin, AreaBehaviorBase):
    def __init__(self):
        super().__init__()
        self.trades = defaultdict(list)  # type: Dict[Market, List[Trade]]

    def energy_balance(self, market, *, allow_open_market=False):
        """
        Return own energy balance for a particular market.

        Negative values indicate bought energy, postive ones sold energy.
        """
        if not allow_open_market and not market.readonly:
            raise ValueError(
                'Energy balance for open market requested and `allow_open_market` no passed')
        return sum(
            t.offer.energy * -1
            if t.buyer == self.owner.name
            else t.offer.energy
            for t in self.trades[market]
        )

    def accept_offer(self, market: Market, offer, buyer=None):
        if buyer is None:
            buyer = self.owner.name
        trade = market.accept_offer(offer, buyer)
        self.trades[market].append(trade)
        return trade
