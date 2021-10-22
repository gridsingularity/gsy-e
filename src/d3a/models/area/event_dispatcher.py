"""
Copyright 2018 Grid Singularity
This file is part of D3A.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
from logging import getLogger
from typing import Union, Dict, TYPE_CHECKING, Optional

from d3a_interface.constants_limits import ConstSettings
from d3a_interface.enums import SpotMarketTypeEnum
from numpy.random import random
from pendulum import DateTime

from d3a import constants
from d3a.d3a_core.exceptions import WrongMarketTypeException
from d3a.d3a_core.redis_connections.redis_area_market_communicator import RedisCommunicator
from d3a.d3a_core.util import create_subdict_or_update
from d3a.events.event_structures import MarketEvent, AreaEvent
from d3a.models.area.redis_dispatcher.area_event_dispatcher import RedisAreaEventDispatcher
from d3a.models.area.redis_dispatcher.area_to_market_publisher import AreaToMarketEventPublisher
from d3a.models.area.redis_dispatcher.market_event_dispatcher import AreaRedisMarketEventDispatcher
from d3a.models.area.redis_dispatcher.market_notify_event_subscriber import (
    MarketNotifyEventSubscriber)
from d3a.models.market import Market
from d3a.models.market.market_structures import AvailableMarketTypes
from d3a.models.strategy.area_agents.balancing_agent import BalancingAgent
from d3a.models.strategy.area_agents.future_agent import FutureAgent
from d3a.models.strategy.area_agents.one_sided_agent import OneSidedAgent
from d3a.models.strategy.area_agents.one_sided_alternative_pricing_agent import (
    OneSidedAlternativePricingAgent)
from d3a.models.strategy.area_agents.settlement_agent import SettlementAgent
from d3a.models.strategy.area_agents.two_sided_agent import TwoSidedAgent
from d3a.models.strategy.area_agents.inter_area_agent import InterAreaAgent

if TYPE_CHECKING:
    from d3a.models.area import Area

log = getLogger(__name__)

EVENT_DISPATCHING_VIA_REDIS = ConstSettings.GeneralSettings.EVENT_DISPATCHING_VIA_REDIS


class AreaDispatcher:
    """Handle dispatching of area and market events between areas via inter area agents."""
    def __init__(self, area):
        self._inter_area_agents: Dict[DateTime, Dict[str, OneSidedAgent]] = {}
        self._balancing_agents: Dict[DateTime, Dict[str, BalancingAgent]] = {}
        self._settlement_agents: Dict[DateTime, Dict[str, SettlementAgent]] = {}
        self.future_agents: Dict[FutureAgent] = {}
        self.area = area

    @property
    def interarea_agents(self) -> Dict[DateTime, Dict[str, OneSidedAgent]]:
        """Return dict of inter area agents for spot markets."""
        return self._inter_area_agents

    @property
    def balancing_agents(self) -> Dict[DateTime, Dict[str, BalancingAgent]]:
        """Return dict of inter area agents for balancing markets."""
        return self._balancing_agents

    @property
    def settlement_agents(self) -> Dict[DateTime, Dict[str, SettlementAgent]]:
        """Return dict of inter area agents for settlement markets."""
        return self._settlement_agents

    def broadcast_activate(self, **kwargs):
        """Trigger broadcasting if the ACTIVATE event."""
        return self._broadcast_notification(AreaEvent.ACTIVATE, **kwargs)

    def broadcast_tick(self, **kwargs):
        """Trigger broadcasting if the TICK event."""
        return self._broadcast_notification(AreaEvent.TICK, **kwargs)

    def broadcast_market_cycle(self, **kwargs):
        """Trigger broadcasting if the MARKET_CYCLE event."""
        return self._broadcast_notification(AreaEvent.MARKET_CYCLE, **kwargs)

    def broadcast_balancing_market_cycle(self, **kwargs):
        """""Trigger broadcasting if the BALANCING_MARKET_CYCLE event."""
        return self._broadcast_notification(AreaEvent.BALANCING_MARKET_CYCLE, **kwargs)

    @property
    def broadcast_callback(self):
        """Return actual function for broadcasting of events to be overwritten by subclasses."""
        return self._broadcast_notification

    def _broadcast_notification_to_agents_of_future_markets(self, event_type: AreaEvent,
                                                            **kwargs) -> None:
        for agent in self.future_agents.values():
            if not self.area.events.is_connected:
                break
            agent.event_listener(event_type, **kwargs)

    def _broadcast_notification_to_agents_of_market_type(
            self, market_type: AvailableMarketTypes, event_type: AreaEvent, **kwargs) -> None:
        for time_slot, agents in self._get_agents_for_market_type(self, market_type).items():
            if time_slot not in self.area._markets.get_market_instances_from_class_type(
                    market_type):
                # exclude past IAAs
                continue

            if not self.area.events.is_connected:
                break
            for area_name in sorted(agents, key=lambda _: random()):
                agents[area_name].event_listener(event_type, **kwargs)

    def _broadcast_notification(self, event_type: Union[MarketEvent, AreaEvent], **kwargs) -> None:
        if (not self.area.events.is_enabled and
                event_type not in [AreaEvent.ACTIVATE, AreaEvent.MARKET_CYCLE]):
            return

        # Broadcast to children in random order to ensure fairness
        for child in sorted(self.area.children, key=lambda _: random()):
            child.dispatcher.event_listener(event_type, **kwargs)
        self._broadcast_notification_to_agents_of_market_type(
            AvailableMarketTypes.SPOT, event_type, **kwargs)
        self._broadcast_notification_to_agents_of_market_type(
            AvailableMarketTypes.BALANCING, event_type, **kwargs)
        self._broadcast_notification_to_agents_of_market_type(
            AvailableMarketTypes.SETTLEMENT, event_type, **kwargs)
        self._broadcast_notification_to_agents_of_future_markets(event_type, **kwargs)

    def _should_dispatch_to_strategies(self, event_type: Union[MarketEvent, AreaEvent]) -> bool:
        return (True if event_type is AreaEvent.ACTIVATE
                else self.area.events.is_connected and self.area.events.is_enabled)

    def event_listener(self, event_type: Union[MarketEvent, AreaEvent], **kwargs) -> None:
        """
        Call the corresponding events in the connected area dependent on the event_type.
        Args:
            event_type: Decides which event method to be called in the Area class
            **kwargs: optional arguments to be passed to the event methods in the area

        Returns:

        """
        if event_type is AreaEvent.TICK and \
                self._should_dispatch_to_strategies(event_type):
            self.area.tick_and_dispatch()
        if event_type is AreaEvent.MARKET_CYCLE:
            self.area.cycle_markets(_trigger_event=True)
        elif event_type is AreaEvent.ACTIVATE:
            self.area.activate(**kwargs)
        if self._should_dispatch_to_strategies(event_type):
            if self.area.strategy:
                self.area.strategy.event_listener(event_type, **kwargs)
        elif (not self.area.events.is_enabled or not self.area.events.is_connected) \
                and event_type == AreaEvent.MARKET_CYCLE and self.area.strategy is not None:
            self.area.strategy.event_on_disabled_area()

    @staticmethod
    def _create_agent_object(owner: "Area",
                             higher_market: Market,
                             lower_market: Market,
                             market_type: AvailableMarketTypes) -> Optional[InterAreaAgent]:
        agent_constructor_arguments = {
            "owner": owner,
            "higher_market": higher_market,
            "lower_market": lower_market,
            "min_offer_age": ConstSettings.IAASettings.MIN_OFFER_AGE
        }

        if market_type == AvailableMarketTypes.SPOT:
            if ConstSettings.IAASettings.MARKET_TYPE == SpotMarketTypeEnum.ONE_SIDED.value:
                if ConstSettings.IAASettings.AlternativePricing.PRICING_SCHEME != 0:
                    return OneSidedAlternativePricingAgent(**agent_constructor_arguments)
                return OneSidedAgent(**agent_constructor_arguments)
            if ConstSettings.IAASettings.MARKET_TYPE == SpotMarketTypeEnum.TWO_SIDED.value:
                return TwoSidedAgent(
                    **agent_constructor_arguments,
                    min_bid_age=ConstSettings.IAASettings.MIN_BID_AGE
                )
            raise WrongMarketTypeException("Wrong market type setting flag "
                                           f"{ConstSettings.IAASettings.MARKET_TYPE}")
        if market_type == AvailableMarketTypes.SETTLEMENT:
            return SettlementAgent(**agent_constructor_arguments)
        if market_type == AvailableMarketTypes.BALANCING:
            return BalancingAgent(**agent_constructor_arguments)
        if market_type == AvailableMarketTypes.FUTURE:
            return FutureAgent(**agent_constructor_arguments,
                               min_bid_age=ConstSettings.IAASettings.MIN_BID_AGE)

        assert False, f"Market type not supported {market_type}"

    @staticmethod
    def _get_agents_for_market_type(dispatcher_object: "AreaDispatcher",
                                    market_type: AvailableMarketTypes):
        if market_type == AvailableMarketTypes.SPOT:
            return dispatcher_object.interarea_agents
        if market_type == AvailableMarketTypes.BALANCING:
            return dispatcher_object.balancing_agents
        if market_type == AvailableMarketTypes.SETTLEMENT:
            return dispatcher_object.settlement_agents

        assert False, f"Market type not supported {market_type}"

    def _create_area_agents_for_market_type(self, market: Market,
                                            market_type: AvailableMarketTypes) -> None:
        interarea_agents = self._get_agents_for_market_type(self, market_type)
        parent_markets = self.area.parent._markets.get_market_instances_from_class_type(
            market_type)
        if market.time_slot in interarea_agents or market.time_slot not in parent_markets:
            return

        iaa = self._create_agent_object(
            owner=self.area,
            higher_market=parent_markets[market.time_slot],
            lower_market=market,
            market_type=market_type
        )

        # Attach agent to own IAA list
        create_subdict_or_update(interarea_agents, market.time_slot, {self.area.name: iaa})

        parent_interarea_agents = self._get_agents_for_market_type(
            self.area.parent.dispatcher, market_type)
        # And also to parents to allow events to flow from both markets
        create_subdict_or_update(parent_interarea_agents, market.time_slot, {self.area.name: iaa})

    def create_area_agents_for_future_markets(self, market: Market) -> None:
        """Create area agents for future markets There should only be one per Area at any time."""
        if self.area.name in self.future_agents or not self.area.parent:
            return

        iaa = self._create_agent_object(
            owner=self.area,
            higher_market=self.area.parent._markets.future_markets,
            lower_market=market,
            market_type=AvailableMarketTypes.FUTURE
        )

        self.future_agents[self.area.name] = iaa
        self.area.parent.dispatcher.future_agents[self.area.name] = iaa

    def create_area_agents(self, market_type: AvailableMarketTypes, market: Market):
        """Create area agents dependent on the market type."""
        if not self.area.parent:
            return
        if self.area.strategy:
            return
        if not self.area.parent.events.is_connected:
            return
        if not self.area.children:
            return

        self._create_area_agents_for_market_type(market, market_type)

    def _delete_past_agents(self, area_agent_member: Dict) -> None:
        if not constants.RETAIN_PAST_MARKET_STRATEGIES_STATE:
            delete_agents = [pm for pm in area_agent_member.keys() if
                             self.area.current_market and pm < self.area.current_market.time_slot]
            for pm in delete_agents:
                for area_name in area_agent_member[pm]:
                    agent = area_agent_member[pm][area_name]
                    if hasattr(agent, "engines"):
                        agent.delete_engines()
                        del agent.engines
                    agent.higher_market = None
                    agent.lower_market = None
                del area_agent_member[pm]


class RedisAreaDispatcher(AreaDispatcher):
    """
    Handle dispatching of area and market events between areas via inter area agents
    based communication via redis.
    """
    def __init__(self, area, redis_area, redis_market):
        super().__init__(area)
        self.area_event_dispatcher = RedisAreaEventDispatcher(area, self, redis_area)
        self.market_event_dispatcher = AreaRedisMarketEventDispatcher(area, self, redis_market)
        self.market_notify_event_dispatcher = MarketNotifyEventSubscriber(area, self)
        self.area_to_market_event_dispatcher = AreaToMarketEventPublisher(area)

    def publish_market_clearing(self):
        """Trigger sending market_clearing event via redis."""
        self.area_to_market_event_dispatcher.publish_markets_clearing()

    def broadcast_activate(self, **kwargs):
        """Trigger broadcasting if the ACTIVATE event."""
        self._broadcast_events(AreaEvent.ACTIVATE, **kwargs)

    def broadcast_tick(self, **kwargs):
        """Trigger broadcasting if the TICK event."""
        return self._broadcast_events(AreaEvent.TICK, **kwargs)

    def broadcast_market_cycle(self, **kwargs):
        """Trigger broadcasting if the MARKET_CYCLE event."""
        self.market_notify_event_dispatcher.cycle_market_channels()
        return self._broadcast_events(AreaEvent.MARKET_CYCLE, **kwargs)

    def broadcast_balancing_market_cycle(self, **kwargs):
        """Trigger broadcasting if the BALANCING_MARKET_CYCLE event."""
        return self._broadcast_events(AreaEvent.BALANCING_MARKET_CYCLE, **kwargs)

    def _broadcast_events(self, event_type, **kwargs):
        if isinstance(event_type, AreaEvent):
            self.area_event_dispatcher.broadcast_event_redis(event_type, **kwargs)
        elif isinstance(event_type, MarketEvent):
            self.market_event_dispatcher.broadcast_event_redis(event_type, **kwargs)
        else:
            assert False, f"Event type {event_type} is not an Area or Market event."

    @property
    def broadcast_callback(self):
        """Return actual function for broadcasting of events (overwrites superclass)."""
        return self._broadcast_events


class DispatcherFactory:
    """Create different dispatcher class depending on the general settings."""
    def __init__(self, area):
        self.event_dispatching_via_redis = \
            ConstSettings.GeneralSettings.EVENT_DISPATCHING_VIA_REDIS
        self.dispatcher = \
            RedisAreaDispatcher(area, RedisCommunicator(), RedisCommunicator()) \
            if self.event_dispatching_via_redis \
            else AreaDispatcher(area)

    def __call__(self):
        return self.dispatcher
