from logging import getLogger
from random import random
from typing import Dict, List, Union  # noqa

from pendulum.pendulum import Pendulum

from d3a.models.events import AreaEvent, MarketEvent
from d3a.models.market import Market
from d3a.models.strategy import BaseStrategy
from d3a.util import TaggedLogWrapper


log = getLogger(__name__)


MARKET_SLOT_LENGTH = 15  # minutes
MARKET_SLOT_COUNT = 4


class Area:
    def __init__(self, name: str = None, children: List["Area"] = None,
                 strategy: BaseStrategy = None):
        self.active = False
        self.log = TaggedLogWrapper(log, name)
        self.name = name
        self.parent = None
        self.children = children if children is not None else []
        for child in self.children:
            child.parent = self
        self.inter_area_agents = {}  # type: Dict[Market, InterAreaAgent]
        self.strategy = strategy
        if self.strategy:
            self.strategy.area = self
        else:
            self.log.warning("Strategy missing")
        # Children trade in `markets`
        self.markets = {}  # type: Dict[Pendulum, Market]
        # Past markets
        self.past_markets = {}  # type: Dict[Pendulum, Market]

    def activate(self):
        if self.parent is None:
            # On the top level we use `activate` to also trigger
            # the initial market creation (which will trickle down it's own event chain).
            self._cycle_markets()
        self.log.info('Activating area')
        self.active = True
        self._broadcast_notification(AreaEvent.ACTIVATE)

    def __repr__(self):
        return "<Area '{s.name}' markets: {markets}>".format(
            s=self,
            markets=[t.strftime("%H:%M") for t in self.markets.keys()]
        )

    def _cycle_markets(self):
        """
        Remove markets for old time slots, add markets for new slots.
        Trigger `MARKET_CYCLE` event to allow child markets to also cycle.

        It's important for this to happen from top to bottom of the `Area` tree
        in order for the `InterAreaAgent`s to be connected correctly
        """
        now = self.get_now()
        now = now.with_time(
            now.hour,
            (now.minute // MARKET_SLOT_LENGTH) * MARKET_SLOT_LENGTH,
            second=0
        )
        past_limit = now.subtract(minutes=MARKET_SLOT_LENGTH)

        self.log.info("Cycling markets")
        changed = False

        # Remove timed out markets
        # We use `list()` here to get a copy since we modify the market list in-place
        for timeframe in list(self.past_markets.keys()):
            if timeframe < past_limit:
                market = self.markets.pop(timeframe)
                changed = True
                self.log.info("Removing {t:%H:%M} market".format(t=timeframe))

        # Move old and current markets to `past_markets`
        # We use `list()` here to get a copy since we modify the market list in-place
        for timeframe in list(self.markets.keys()):
            if timeframe <= now:
                market = self.markets.pop(timeframe)
                market.readonly = True
                # Remove inter area agent
                self.inter_area_agents.pop(market, None)
                self.past_markets[timeframe] = market
                changed = True
                self.log.info("Moving {t:%H:%M} market to past".format(t=timeframe))

        # Markets range from one slot to MARKET_SLOT_COUNT into the future
        for offset in range(MARKET_SLOT_LENGTH, MARKET_SLOT_LENGTH * MARKET_SLOT_COUNT,
                            MARKET_SLOT_LENGTH):
            timeframe = now.add(minutes=offset)
            if timeframe not in self.markets:
                # Create markets for missing slots
                market = Market(notification_listener=self._broadcast_notification)
                if market not in self.inter_area_agents:
                    if self.parent and timeframe in self.parent.markets:
                        self.inter_area_agents[market] = InterAreaAgent(
                            self.parent.markets[timeframe],
                            market
                        )
                self.markets[timeframe] = market
                changed = True
                self.log.info("Adding {t:%H:%M} market".format(t=timeframe))
        if changed:
            self._broadcast_notification(AreaEvent.MARKET_CYCLE)

    def get_now(self):
        """
        Return the 'current time' as a `Pendulum` object.
        Can be overridden in subclasses to change the meaning of 'now'.
        """
        return Pendulum.now()

    def tick(self):
        self._broadcast_notification(AreaEvent.TICK, area=self)

    def _broadcast_notification(self, event_type: Union[MarketEvent, AreaEvent], **kwargs):
        # Broadcast to children in random order to ensure fairness
        for child in sorted(self.children, key=lambda _: random()):
            child.event_listener(event_type, **kwargs)
        for agent in self.inter_area_agents.values():
            agent.event_listener(event_type, **kwargs)

    def event_listener(self, event_type: Union[MarketEvent, AreaEvent], **kwargs):
        if event_type is AreaEvent.TICK:
            self.tick()
        elif event_type is AreaEvent.MARKET_CYCLE:
            self._cycle_markets()
        elif event_type is AreaEvent.ACTIVATE:
            self.activate()
        if self.strategy:
            self.strategy.event_listener(event_type, **kwargs)


class InterAreaAgent:
    def __init__(self, source_market, target_market):
        self.source_market = source_market
        self.target_market = target_market

    def event_listener(self, event_type: Union[MarketEvent, AreaEvent], **kwargs):
        pass


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
