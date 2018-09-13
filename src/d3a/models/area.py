import warnings
from collections import OrderedDict, defaultdict
from logging import getLogger
from random import random
from typing import Dict, List, Optional, Union  # noqa

from cached_property import cached_property
from pendulum import duration
from pendulum import DateTime
from slugify import slugify

from d3a.exceptions import AreaException
from d3a.models.appliance.base import BaseAppliance
from d3a.models.appliance.inter_area import InterAreaAppliance
from d3a.models.config import SimulationConfig
from d3a.models.events import AreaEvent, MarketEvent, TriggerMixin
from d3a.models.market import Market, BalancingMarket
from d3a.models.strategy.base import BaseStrategy
from d3a.models.strategy.inter_area import InterAreaAgent, BalancingAgent
from d3a.util import TaggedLogWrapper
from d3a.models.strategy.const import ConstSettings
from d3a import TIME_FORMAT

log = getLogger(__name__)


DEFAULT_CONFIG = SimulationConfig(
    duration=duration(hours=24),
    market_count=4,
    slot_length=duration(minutes=15),
    tick_length=duration(seconds=1),
    cloud_coverage=ConstSettings.DEFAULT_PV_POWER_PROFILE,
    market_maker_rate=str(ConstSettings.DEFAULT_MARKET_MAKER_RATE),
    iaa_fee=ConstSettings.INTER_AREA_AGENT_FEE_PERCENTAGE
)


class Area:
    _area_id_counter = 1

    def __init__(self, name: str = None, children: List["Area"] = None,
                 strategy: BaseStrategy = None,
                 appliance: BaseAppliance = None,
                 config: SimulationConfig = None,
                 budget_keeper=None):
        self.active = False
        self.log = TaggedLogWrapper(log, name)
        self.current_tick = 0
        self.name = name
        self.slug = slugify(name, to_lower=True)
        self.area_id = Area._area_id_counter
        Area._area_id_counter += 1
        self.parent = None
        self.children = children if children is not None else []
        for child in self.children:
            child.parent = self
        self.inter_area_agents = \
            defaultdict(list)  # type: Dict[Market, List[InterAreaAgent]]
        self.balancing_agents = \
            defaultdict(list)  # type: Dict[BalancingMarket, List[BalancingAgent]]
        self.strategy = strategy
        self.appliance = appliance
        self._config = config

        self.budget_keeper = budget_keeper
        if budget_keeper:
            self.budget_keeper.area = self
        # Children trade in `markets`
        self.markets = OrderedDict()  # type: Dict[DateTime, Market]
        self.balancing_markets = OrderedDict()  # type: Dict[DateTime, BalancingMarket]
        # Past markets
        self.past_markets = OrderedDict()  # type: Dict[DateTime, Market]
        self.past_balancing_markets = OrderedDict()  # type: Dict[DateTime, BalancingMarket]
        self.listeners = []
        self._accumulated_past_price = 0
        self._accumulated_past_energy = 0

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

            if self.budget_keeper:
                self.budget_keeper.activate()

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
            markets=[t.strftime(TIME_FORMAT) for t in self.markets.keys()]
        )

    @cached_property
    def current_market(self) -> Optional[Market]:
        """Returns the 'current' market (i.e. the one currently 'running')"""
        try:
            return list(self.past_markets.values())[-1]
        except IndexError:
            return None

    @property
    def next_market(self) -> Optional[Market]:
        """Returns the 'current' market (i.e. the one currently 'running')"""
        try:
            return list(self.markets.values())[0]
        except IndexError:
            return None

    @property
    def current_slot(self):
        return self.current_tick // self.config.ticks_per_slot

    @property
    def current_tick_in_slot(self):
        return self.current_tick % self.config.ticks_per_slot

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
    def historical_avg_rate(self):
        price = sum(
            market.accumulated_trade_price
            for market in self.markets.values()
        ) + self._accumulated_past_price
        energy = sum(
            market.accumulated_trade_energy
            for market in self.markets.values()
        ) + self._accumulated_past_energy
        return price / energy if energy else 0

    @property
    def cheapest_offers(self):
        cheapest_offers = []
        for market in self.markets.values():
            cheapest_offers.extend(market.sorted_offers[0:1])
        return cheapest_offers

    @property
    def market_with_most_expensive_offer(self):
        # In case of a tie, max returns the first market occurrence in order to
        # satisfy the most recent market slot
        return max(self.markets.values(),
                   key=lambda m: m.sorted_offers[0].price / m.sorted_offers[0].energy)

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

    @cached_property
    def child_by_slug(self):
        slug_map = {}
        areas = [self]
        while areas:
            for area in list(areas):
                slug_map[area.slug] = area
                areas.remove(area)
                areas.extend(area.children)
        return slug_map

    def _cycle_markets(self, _trigger_event=True, _market_cycle=False):
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

        if self.budget_keeper and _market_cycle:
            self.budget_keeper.process_market_cycle()

        now = self.now
        time_in_hour = duration(minutes=now.minute, seconds=now.second)
        now = now.at(now.hour, minute=0, second=0) + \
            ((time_in_hour // self.config.slot_length) * self.config.slot_length)

        self.log.info("Cycling markets")
        changed = False

        # Move old and current markets to `past_markets`
        # We use `list()` here to get a copy since we modify the market list in-place
        first = True
        for timeframe in list(self.markets.keys()):
            if timeframe < now:
                market = self.markets.pop(timeframe)
                market.readonly = True
                balancing_market = self.balancing_markets.pop(timeframe)
                balancing_market.readonly = True
                self.past_markets[timeframe] = market
                if not first:
                    # Remove inter area agent & balancing_agent
                    self.inter_area_agents.pop(market, None)
                    self.balancing_agents.pop(balancing_market, None)
                else:
                    first = False
                changed = True
                self.log.debug("Moving {t:%H:%M} market to past".format(t=timeframe))
                self.log.debug("Moving {t:%H:%M} balancing_market to past".format(t=timeframe))

        self._accumulated_past_price = sum(
            market.accumulated_trade_price
            for market in self.past_markets.values()
        )
        self._accumulated_past_energy = sum(
            market.accumulated_trade_energy
            for market in self.past_markets.values()
        )
        # Clear `current_market` cache
        self.__dict__.pop('current_market', None)

        # Markets range from one slot to MARKET_SLOT_COUNT into the future
        for offset in (self.config.slot_length * i for i in range(self.config.market_count)):
            timeframe = now + offset
            if timeframe not in self.markets:
                # Create markets for missing slots
                market = Market(timeframe, self,
                                notification_listener=self._broadcast_notification)
                if market not in self.inter_area_agents:
                    if self.parent and timeframe in self.parent.markets and not self.strategy:
                        # Only connect an InterAreaAgent if we have a parent, a corresponding
                        # timeframe market exists in the parent and we have no strategy
                        iaa = InterAreaAgent(
                            owner=self,
                            higher_market=self.parent.markets[timeframe],
                            lower_market=market,
                            transfer_fee_pct=self.config.iaa_fee
                        )
                        # Attach agent to own IAA list
                        self.inter_area_agents[market].append(iaa)
                        # And also to parents to allow events to flow form both markets
                        self.parent.inter_area_agents[self.parent.markets[timeframe]].append(iaa)
                        if self.parent:
                            # Add inter area appliance to report energy
                            self.appliance = InterAreaAppliance(self.parent, self)
                self.markets[timeframe] = market
                changed = True
                self.log.debug("Adding {t:{format}} market".format(
                    t=timeframe,
                    format="%H:%M" if self.config.slot_length.total_seconds() > 60 else "%H:%M:%S"
                ))
                if timeframe not in self.balancing_markets:
                    # Create balancing_markets for missing slots
                    balancing_market = \
                        BalancingMarket(timeframe, self,
                                        notification_listener=self._broadcast_notification)
                    if balancing_market not in self.balancing_agents:
                        if self.parent and timeframe in self.parent.balancing_markets \
                                and not self.strategy:
                            # Only connect BalancingAgent if we have a parent,
                            # a corresponding timeframe balancing_market exists in the parent
                            # and we have no strategy
                            baa = BalancingAgent(
                                owner=self,
                                higher_market=self.parent.balancing_markets[timeframe],
                                lower_market=balancing_market,
                                transfer_fee_pct=self.config.iaa_fee
                            )
                            # Attach agent to own BA list
                            self.balancing_agents[balancing_market].append(baa)
                            parent_balancing_markets = self.parent.balancing_markets[timeframe]
                            # And also to parents to allow events to flow form both markets
                            self.parent.balancing_agents[parent_balancing_markets].append(baa)
                            if self.parent:
                                # Add inter area appliance to report energy
                                self.appliance = InterAreaAppliance(self.parent, self)
                    self.balancing_markets[timeframe] = balancing_market
                    changed = True
                    format = \
                        "%H:%M" if self.config.slot_length.total_seconds() > 60 else "%H:%M:%S"
                    self.log.debug("Adding {t:{format}} balancing_market".format(
                        t=timeframe,
                        format=format))

        # Force market cycle event in case this is the first market slot
        if (changed or len(self.past_markets.keys()) == 0) and _trigger_event:
            self._broadcast_notification(AreaEvent.MARKET_CYCLE)

    def get_now(self) -> DateTime:
        """Compatibility wrapper"""
        warnings.warn("The '.get_now()' method has been replaced by the '.now' property. "
                      "Please use that in the future.")
        return self.now

    @property
    def now(self) -> DateTime:
        """
        Return the 'current time' as a `DateTime` object.
        Can be overridden in subclasses to change the meaning of 'now'.

        In this default implementation 'current time' is defined by the number of ticks that
        have passed.
        """
        return DateTime.now().start_of('day').add(
            seconds=self.config.tick_length.seconds * self.current_tick
        )

    @cached_property
    def available_triggers(self):
        triggers = []
        if isinstance(self.strategy, TriggerMixin):
            triggers.extend(self.strategy.available_triggers)
        if isinstance(self.appliance, TriggerMixin):
            triggers.extend(self.appliance.available_triggers)
        return {t.name: t for t in triggers}

    def tick(self):
        if self.current_tick % self.config.ticks_per_slot == 0:
            self._cycle_markets()
        self._broadcast_notification(AreaEvent.TICK, area=self)
        self.current_tick += 1

    def report_accounting(self, market, reporter, value, time=None):
        if time is None:
            time = self.now
        slot = market.time_slot
        if slot in self.markets or slot in self.past_markets:
            market.set_actual_energy(time, reporter, value)
        else:
            raise RuntimeError("Reporting energy for unknown market")

    def _broadcast_notification(self, event_type: Union[MarketEvent, AreaEvent], **kwargs):
        # Broadcast to children in random order to ensure fairness
        for child in sorted(self.children, key=lambda _: random()):
            child.event_listener(event_type, **kwargs)
        # Also broadcast to IAAs. Again in random order
        for market, agents in self.inter_area_agents.items():
            if market.time_slot not in self.markets:
                # exclude past IAAs
                continue

            for agent in sorted(agents, key=lambda _: random()):
                agent.event_listener(event_type, **kwargs)
        for listener in self.listeners:
            listener.event_listener(event_type, **kwargs)

    def _fire_trigger(self, trigger_name, **params):
        for target in (self.strategy, self.appliance):
            if isinstance(target, TriggerMixin):
                for trigger in target.available_triggers:
                    if trigger.name == trigger_name:
                        return target.fire_trigger(trigger_name, **params)

    def add_listener(self, listener):
        self.listeners.append(listener)

    def event_listener(self, event_type: Union[MarketEvent, AreaEvent], **kwargs):
        if event_type is AreaEvent.TICK:
            self.tick()
        elif event_type is AreaEvent.MARKET_CYCLE:
            self._cycle_markets(_market_cycle=True)
        elif event_type is AreaEvent.ACTIVATE:
            self.activate()
        if self.strategy:
            self.strategy.event_listener(event_type, **kwargs)
        if self.appliance:
            self.appliance.event_listener(event_type, **kwargs)
