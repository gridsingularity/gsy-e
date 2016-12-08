from logging import getLogger
from typing import Union

from cached_property import cached_property

from d3a.models.events import AreaEvent, MarketEvent
from d3a.util import TaggedLogWrapper


log = getLogger(__name__)


class BaseStrategy:
    def __init__(self):
        # `area` is the area we trade in
        self.area = None
        # `owner` is the area of which we are the strategy, usually a child of `area`
        self.owner = None

    @property
    def log(self):
        if not self.owner:
            log.warning("Logging without area in %s, using default logger",
                        self.__class__.__name__, stack_info=True)
            return log
        return self._log

    @cached_property
    def _log(self):
        return TaggedLogWrapper(log, "{s.owner.name}:{s.__class__.__name__}".format(s=self))

    def event_listener(self, event_type: Union[AreaEvent, MarketEvent], **kwargs):
        self.log.debug("Dispatching event %s", event_type.name)
        getattr(self, "event_{}".format(event_type.name.lower()))(**kwargs)

    def event_tick(self, *, area):
        pass

    def event_market_cycle(self):
        pass

    def event_activate(self):
        pass

    def event_offer(self, *, market, offer):
        pass

    def event_offer_deleted(self, *, market, offer):
        pass

    def event_trade(self, *, market, trade):
        pass
