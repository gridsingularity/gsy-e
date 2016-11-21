from enum import Enum
from logging import getLogger
from typing import Dict, List, Union  # noqa

from pendulum.pendulum import Pendulum

from d3a.models.events import AreaEvent, MarketEvent
from d3a.models.market import Market
from d3a.models.strategy import BaseStrategy
from d3a.util import TaggedLogWrapper

log = getLogger(__name__)


MARKET_SLOT_LENGTH = 15  # minutes
MARKET_SLOT_COUNT = 4


class AreaEvent(Enum):
    MARKET_CYCLE = 1


class Area:
    def __init__(self, name: str = None, children: List["Area"] = None,
                 strategy: BaseStrategy = None):
        self.log = TaggedLogWrapper(log, name)
        self.name = name
        self.parent = None
        self.children = children if children is not None else []
        for child in self.children:
            child.parent = self
        self.strategy = strategy
        # Chidren trade in `markets`
        self.markets = {}  # type: Dict[Pendulum, Market]
        self._cycle_markets()

    def _cycle_markets(self):
        now = Pendulum.now()
        now = now.with_time(
            now.hour,
            (now.minute // MARKET_SLOT_LENGTH) * MARKET_SLOT_LENGTH,
            second=0
        )
        past_limit = now.subtract(minutes=MARKET_SLOT_LENGTH)

        self.log.info("Cycling markets")
        changed = False

        # Remove old markets
        # We use `list()` here to get a copy since we modify the market list in-place
        for timeframe in list(self.markets.keys()):
            if timeframe < past_limit:
                del self.markets[timeframe]
                changed = True
                self.log.info("Removing {t:%H:%M} market".format(t=timeframe))

        for offset in range(-MARKET_SLOT_LENGTH, MARKET_SLOT_LENGTH * MARKET_SLOT_COUNT,
                            MARKET_SLOT_LENGTH):
            timeframe = now.add(minutes=offset)
            if timeframe not in self.markets:
                # Create markets for missing slots
                self.markets[timeframe] = Market(self._broadcast_notification)
                changed = True
                if offset <= 0:
                    self.log.info("Adding [{t:%H:%M}] market".format(t=timeframe))
                else:
                    self.log.info("Adding {t:%H:%M} market".format(t=timeframe))
            if offset <= 0:
                # Mark past/current markets as readonly
                self.markets[timeframe].readonly = True
        if changed:
            self._broadcast_notification(AreaEvent.MARKET_CYCLE)

    def _broadcast_notification(self, event_type: Union[MarketEvent, AreaEvent], *args):
        for child in self.children:
            child.event_listener(event_type, *args)

    def event_listener(self, event_type: Union[MarketEvent, AreaEvent], *args):
        if event_type is AreaEvent.MARKET_CYCLE:
            self._cycle_markets()
        if self.strategy:
            self.strategy.event_listener(event_type, *args)


class InterAreaAgent:
    def __init__(self, area1, area2):
        ...


class GridArea(Area):
    ...


class PowerStationArea(Area):
    ...


class HouseArea(Area):
    ...


class PVArea(Area):
    ...


class FridgeArea(Area):
    ...
