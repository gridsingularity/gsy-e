import warnings
from collections import OrderedDict, defaultdict
from logging import getLogger
from random import random
from typing import Dict, List, Optional, Union  # noqa

from cached_property import cached_property
from pendulum import duration
from pendulum import DateTime
from slugify import slugify

from d3a.blockchain import BlockChainInterface
from d3a import TIME_ZONE
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
    market_count=1,
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
                 budget_keeper=None,
                 balancing_spot_trade_ratio=ConstSettings.BALANCING_SPOT_TRADE_RATIO):
        self.balancing_spot_trade_ratio = balancing_spot_trade_ratio
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
        self._bc = None  # type: BlockChainInterface
        self.listeners = []
        self._accumulated_past_price = 0
        self._accumulated_past_energy = 0

    def activate(self, bc=None):
        if bc:
            self._bc = bc
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
    def bc(self) -> Optional[BlockChainInterface]:
        if self._bc is not None:
            return self._bc
        if self.parent:
            return self.parent.bc
        return None

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

        # Move old and current markets & balancing_markets to
        # `past_markets` & past_balancing_markets. We use `list()` here to get a copy since we
        # modify the market list in-place
        changed, _ = self._market_rotation(current_time=now,
                                           markets=self.markets,
                                           past_markets=self.past_markets,
                                           area_agent=self.inter_area_agents)

        changed_balancing_market, _ = \
            self._market_rotation(current_time=now,
                                  markets=self.balancing_markets,
                                  past_markets=self.past_balancing_markets,
                                  area_agent=self.balancing_agents)

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

        # Markets range from one slot to market_count into the future
        changed = self._create_future_markets(current_time=self.now, markets=self.markets,
                                              parent=self.parent,
                                              parent_markets=self.parent.markets
                                              if self.parent is not None else None,
                                              area_agent=self.inter_area_agents,
                                              parent_area_agent=self.parent.inter_area_agents
                                              if self.parent is not None else None,
                                              agent_class=InterAreaAgent,
                                              market_class=Market)

        changed_balancing_market = \
            self._create_future_markets(current_time=self.now, markets=self.balancing_markets,
                                        parent=self.parent,
                                        parent_markets=self.parent.balancing_markets
                                        if self.parent is not None else None,
                                        area_agent=self.balancing_agents,
                                        parent_area_agent=self.parent.balancing_agents
                                        if self.parent is not None else None,
                                        agent_class=BalancingAgent,
                                        market_class=BalancingMarket)

        # Force market cycle event in case this is the first market slot
        if (changed or len(self.past_markets.keys()) == 0) and _trigger_event:
            self._broadcast_notification(AreaEvent.MARKET_CYCLE)

        # Force balancing_market cycle event in case this is the first market slot
        if (changed_balancing_market or len(self.past_balancing_markets.keys()) == 0) \
                and _trigger_event:
            self._broadcast_notification(AreaEvent.BALANCING_MARKET_CYCLE)

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
        return DateTime.now(tz=TIME_ZONE).start_of('day').add(
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
        # Also broadcast to BAs. Again in random order
        for balancing_market, agents in self.balancing_agents.items():
            if balancing_market.time_slot not in self.balancing_markets:
                # exclude past BAs
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
        # TODO: Review this change. Make sure this trigger is not needed anywhere else
        # elif event_type is AreaEvent.MARKET_CYCLE:
        #     self._cycle_markets(_market_cycle=True)
        elif event_type is AreaEvent.ACTIVATE:
            self.activate()
        if self.strategy:
            self.strategy.event_listener(event_type, **kwargs)
        if self.appliance:
            self.appliance.event_listener(event_type, **kwargs)

    def _market_rotation(self, current_time, markets, past_markets, area_agent):
        changed = False
        first = True
        for timeframe in list(markets.keys()):
            if timeframe < current_time:
                market = markets.pop(timeframe)
                market.readonly = True
                past_markets[timeframe] = market
                if not first:
                    # Remove inter area agent
                    area_agent.pop(market, None)
                else:
                    first = False
                changed = True
                self.log.debug("Moving {t:%H:%M} {m} to past"
                               .format(t=timeframe, m=past_markets[timeframe].area.name))
        return changed, first

    def _create_future_markets(self, current_time, markets, parent, parent_markets,
                               area_agent, parent_area_agent, agent_class, market_class):
        changed = False
        for offset in (self.config.slot_length * i for i in range(self.config.market_count)):
            timeframe = current_time + offset
            if timeframe not in markets:
                # Create markets for missing slots
                market = market_class(timeframe, self,
                                      notification_listener=self._broadcast_notification)
                if market not in area_agent:
                    if parent and timeframe in parent_markets and not self.strategy:
                        # Only connect an InterAreaAgent if we have a parent, a corresponding
                        # timeframe market exists in the parent and we have no strategy
                        iaa = agent_class(
                            owner=self,
                            higher_market=parent_markets[timeframe],
                            lower_market=market,
                            transfer_fee_pct=self.config.iaa_fee
                        )
                        # Attach agent to own IAA list
                        area_agent[market].append(iaa)
                        # And also to parents to allow events to flow form both markets
                        parent_area_agent[parent_markets[timeframe]].append(iaa)
                        if parent:
                            # Add inter area appliance to report energy
                            self.appliance = InterAreaAppliance(parent, self)
                markets[timeframe] = market
                changed = True
                self.log.debug("Adding {t:{format}} market".format(
                    t=timeframe,
                    format="%H:%M" if self.config.slot_length.total_seconds() > 60 else "%H:%M:%S"
                ))
        return changed
