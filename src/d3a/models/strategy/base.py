from logging import getLogger
from typing import Dict, Any  # noqa

from d3a.models.base import AreaBehaviorBase
from d3a.models.events import EventMixin
from d3a.models.market import Market  # noqa


log = getLogger(__name__)


class _TradeLookerUpper:
    def __init__(self, owner_name):
        self.owner_name = owner_name

    def __getitem__(self, market):
        for trade in market.trades:
            owner_name = self.owner_name
            if trade.seller == owner_name or trade.buyer == owner_name:
                yield trade


class BaseStrategy(EventMixin, AreaBehaviorBase):
    def __init__(self):
        super().__init__()

    @property
    def trades(self):
        return _TradeLookerUpper(self.owner.name)

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

    def accept_offer(self, market: Market, offer, *, buyer=None, energy=None):
        if buyer is None:
            buyer = self.owner.name
        trade = market.accept_offer(offer, buyer, energy=energy)
        return trade

    def post(self, **data):
        self.event_data_received(data)

    def event_data_received(self, data: Dict[str, Any]):
        pass
