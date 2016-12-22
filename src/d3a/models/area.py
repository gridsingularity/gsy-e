from collections import OrderedDict, defaultdict
from logging import getLogger
from random import random
from typing import Any, Dict, List, Optional, Union  # noqa

from pendulum.interval import Interval
from pendulum.pendulum import Pendulum
from slugify import slugify

from d3a.exceptions import AreaException
from d3a.models.config import SimulationConfig
from d3a.models.events import AreaEvent, MarketEvent
from d3a.models.market import Market
from d3a.models.appliance.base import BaseAppliance
from d3a.models.strategy.base import BaseStrategy
from d3a.models.strategy.inter_area import InterAreaAgent
from d3a.util import TaggedLogWrapper


log = getLogger(__name__)


DEFAULT_CONFIG = SimulationConfig(
    duration=Interval(hours=24),
    market_count=4,
    slot_length=Interval(minutes=15),
    tick_length=Interval(seconds=1)
)


class Area:
    def __init__(self, name: str = None, children: List["Area"] = None,
                 strategy: BaseStrategy = None,
                 appliance: BaseAppliance = None,
                 config: SimulationConfig = None):
        self.active = False
        self.log = TaggedLogWrapper(log, name)
        self.current_tick = 0
        self.name = name
        self.slug = slugify(name, to_lower=True)
        self.parent = None
        self.children = children if children is not None else []
        for child in self.children:
            child.parent = self
        self.inter_area_agents = {}  # type: Dict[Market, InterAreaAgent]
        self.strategy = strategy
        self.appliance = appliance
        self._config = config
        # Children trade in `markets`
        self.markets = OrderedDict()  # type: Dict[Pendulum, Market]
        # Past markets
        self.past_markets = OrderedDict()  # type: Dict[Pendulum, Market]
        # Accounting of used energy per market and time
        self.accounting = defaultdict(
            lambda: defaultdict(list))  # type: Dict[Market, Dict[Pendulum, List[Any]]]

    def activate(self):
        for attr, kind in [(self.strategy, 'Strategy'), (self.appliance, 'Appliance')]:
            if attr:
                if self.parent:
                    attr.area = self.parent
                    attr.owner = self
                else:
                    raise AreaException(
                        "{kind} {attr.__class__.__name__} "
                        "on area {s} without parent!".format(
                            kind=kind,
                            attr=attr,
                            s=self
                        )
                    )

        # Cycle markets without triggering it's own event chain.
        self._cycle_markets(_trigger_event=False)

        if not self.strategy and self.parent is not None:
            self.log.warning("No strategy. Using inter area agent.")
        self.log.info('Activating area')
        self.active = True
        self._broadcast_notification(AreaEvent.ACTIVATE)

    def __repr__(self):
        return "<Area '{s.name}' markets: {markets}>".format(
            s=self,
            markets=[t.strftime("%H:%M") for t in self.markets.keys()]
        )

    @property
    def current_market(self) -> Optional[Market]:
        """Returns the 'current' market (i.e. the one currently 'running')"""
        try:
            return list(self.past_markets.values())[-1]
        except IndexError:
            return None

    @property
    def config(self):
        if self._config:
            return self._config
        if self.parent:
            return self.parent.config
        return DEFAULT_CONFIG

    @property
    def _offer_count(self):
        return sum(
            len(m.offers)
            for markets in (self.past_markets, self.markets)
            for m in markets.values()
        )

    @property
    def _trade_count(self):
        return sum(
            len(m.trades)
            for markets in (self.past_markets, self.markets)
            for m in markets.values()
        )

    @property
    def historical_avg_price(self):
        price = sum(
            t.offer.price
            for market_container in (self.markets.values(), self.past_markets.values())
            for market in market_container
            for t in market.trades
        )
        energy = sum(
            t.offer.energy
            for market_container in (self.markets.values(), self.past_markets.values())
            for market in market_container
            for t in market.trades
        )
        return price / energy if energy else 0

    @property
    def historical_min_max_price(self):
        min_max_prices = [
            (m.min_trade_price, m.max_trade_price)
            for markets in (self.past_markets, self.markets)
            for m in markets.values()
        ]
        return (
            min(p[0] for p in min_max_prices),
            max(p[1] for p in min_max_prices)
        )

    def _cycle_markets(self, _trigger_event=True):
        """
        Remove markets for old time slots, add markets for new slots.
        Trigger `MARKET_CYCLE` event to allow child markets to also cycle.

        It's important for this to happen from top to bottom of the `Area` tree
        in order for the `InterAreaAgent`s to be connected correctly

        `_trigger_event` is used internally to avoid multiple event chains during
        initial area activation.
        """
        if not self.children:
            # Since children trade in markets we only need to populate them if there are any
            return

        now = self.get_now()
        time_in_hour = Interval(minutes=now.minute, seconds=now.second)
        now = now.with_time(now.hour, minute=0, second=0).add_timedelta(
            (time_in_hour // self.config.slot_length) * self.config.slot_length
        )

        self.log.info("Cycling markets")
        changed = False

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
        for offset in (self.config.slot_length * i for i in range(1, self.config.market_count)):
            timeframe = now.add_timedelta(offset)
            if timeframe not in self.markets:
                # Create markets for missing slots
                market = Market(timeframe, self,
                                notification_listener=self._broadcast_notification)
                if market not in self.inter_area_agents:
                    if self.parent and timeframe in self.parent.markets and not self.strategy:
                        # Only connect an InterAreaAgent if we have a parent, a corresponding
                        # timeframe market exists in the parent and we have no strategy
                        self.inter_area_agents[market] = InterAreaAgent(
                            owner=self,
                            higher_market=self.parent.markets[timeframe],
                            lower_market=market
                        )
                self.markets[timeframe] = market
                changed = True
                self.log.info("Adding {t:{format}} market".format(
                    t=timeframe,
                    format="%H:%M" if self.config.slot_length.total_seconds() > 60 else "%H:%M:%S"
                ))
        if changed and _trigger_event:
            self._broadcast_notification(AreaEvent.MARKET_CYCLE)

    def get_now(self) -> Pendulum:
        """
        Return the 'current time' as a `Pendulum` object.
        Can be overridden in subclasses to change the meaning of 'now'.

        In this default implementation 'current time' is defined by the number of ticks that
        have passed.
        """
        return Pendulum.now().start_of('day').add_timedelta(
            self.config.tick_length * self.current_tick
        )

    def tick(self):
        self._broadcast_notification(AreaEvent.TICK, area=self)
        self.current_tick += 1
        if self.current_tick % self.config.ticks_per_slot == 0:
            self._cycle_markets()

    def report_accounting(self, market, reporter, value, time=None):
        if time is None:
            time = self.get_now()
        self.accounting[market][time] = (reporter, value)

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
        if self.appliance:
            self.appliance.event_listener(event_type, **kwargs)
