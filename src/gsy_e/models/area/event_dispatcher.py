"""
Copyright 2018 Grid Singularity
This file is part of Grid Singularity Exchange.

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

from gsy_framework.constants_limits import ConstSettings
from gsy_framework.enums import AvailableMarketTypes
from gsy_framework.enums import SpotMarketTypeEnum
from numpy.random import random
from pendulum import DateTime

from gsy_e.events.event_structures import MarketEvent, AreaEvent
from gsy_e.gsy_e_core.enums import FORWARD_MARKET_TYPES
from gsy_e.gsy_e_core.exceptions import WrongMarketTypeException
from gsy_e.gsy_e_core.redis_connections.area_market import RedisCommunicator
from gsy_e.models.area.redis_dispatcher.area_event_dispatcher import RedisAreaEventDispatcher
from gsy_e.models.area.redis_dispatcher.area_to_market_publisher import AreaToMarketEventPublisher
from gsy_e.models.area.redis_dispatcher.market_event_dispatcher import (
    AreaRedisMarketEventDispatcher)
from gsy_e.models.area.redis_dispatcher.market_notify_event_subscriber import (
    MarketNotifyEventSubscriber)
from gsy_e.models.market import MarketBase
from gsy_e.models.strategy.market_agents.balancing_agent import BalancingAgent
from gsy_e.models.strategy.market_agents.future_agent import FutureAgent
from gsy_e.models.strategy.market_agents.one_sided_agent import OneSidedAgent
from gsy_e.models.strategy.market_agents.settlement_agent import SettlementAgent
from gsy_e.models.strategy.market_agents.two_sided_agent import TwoSidedAgent


if TYPE_CHECKING:
    from gsy_e.models.area import Area

log = getLogger(__name__)

EVENT_DISPATCHING_VIA_REDIS = ConstSettings.GeneralSettings.EVENT_DISPATCHING_VIA_REDIS


class AreaDispatcher:
    """
    Responsible for dispatching the area and market events to the area strategies, and,
    if the area has no strategy, to broadcast the events to the children of the area. Maintain
    dicts with market agents for each market type.
    """
    def __init__(self, area: "Area"):
        self._spot_agents: Dict[DateTime, OneSidedAgent] = {}
        self._balancing_agents: Dict[DateTime, BalancingAgent] = {}
        self._settlement_agents: Dict[DateTime, SettlementAgent] = {}
        self._future_agent: Optional[FutureAgent] = None
        self._forward_agents: Optional[Dict[AvailableMarketTypes, FutureAgent]] = {}
        self.area = area

    @property
    def spot_agents(self) -> Dict[DateTime, OneSidedAgent]:
        """Return market agents of spot markets."""
        return self._spot_agents

    @property
    def balancing_agents(self) -> Dict[DateTime, BalancingAgent]:
        """Return balancing market inter area agents."""
        return self._balancing_agents

    @property
    def future_agent(self):
        """Return the future agent."""
        return self._future_agent

    @property
    def forward_agents(self):
        """Return the forward agents."""
        return self._forward_agents

    @property
    def settlement_agents(self) -> Dict[DateTime, SettlementAgent]:
        """Return settlement market inter area agents."""
        return self._settlement_agents

    def broadcast_activate(self, **kwargs) -> None:
        """
        Send activate event to the event listener of the area, and the event listeners of the
        child areas.
        """
        self.broadcast_notification(AreaEvent.ACTIVATE, **kwargs)

    def broadcast_tick(self, **kwargs) -> None:
        """
        Send tick event to the event listener of the area, and the event listeners of the
        child areas.
        """
        self.broadcast_notification(AreaEvent.TICK, **kwargs)

    def broadcast_market_cycle(self, **kwargs) -> None:
        """
        Send market cycle event to the event listener of the area, and the event listeners of the
        child areas.
        """
        self.broadcast_notification(AreaEvent.MARKET_CYCLE, **kwargs)

    def broadcast_balancing_market_cycle(self, **kwargs) -> None:
        """
        Send balancing market cycle event to the event listener of the area, and the event
        listeners of the child areas.
        """
        self.broadcast_notification(AreaEvent.BALANCING_MARKET_CYCLE, **kwargs)

    def _broadcast_notification_to_single_agent(
            self, agent_area: "Area", market_type: AvailableMarketTypes,
            event_type: AreaEvent, **kwargs) -> None:

        if market_type == AvailableMarketTypes.FUTURE and agent_area.dispatcher.future_agent:
            agent_area.dispatcher.future_agent.event_listener(event_type, **kwargs)
        elif market_type != AvailableMarketTypes.FUTURE:
            agent_dict = self._get_agents_for_market_type(agent_area.dispatcher, market_type)
            for time_slot, agent in agent_dict.items():
                if time_slot not in agent_area.get_market_instances_from_class_type(
                        market_type):
                    # exclude past MAs
                    continue

                agent.event_listener(event_type, **kwargs)

    def _broadcast_notification_to_area_and_child_agents(
            self, market_type: AvailableMarketTypes,
            event_type: Union[MarketEvent, AreaEvent], **kwargs) -> None:

        if not self.area.events.is_connected:
            return

        for child in sorted(self.area.children, key=lambda _: random()):
            if not child.children:
                continue
            self._broadcast_notification_to_single_agent(
                child, market_type, event_type, **kwargs)

        self._broadcast_notification_to_single_agent(
            self.area, market_type, event_type, **kwargs)

    def broadcast_notification(
            self, event_type: Union[MarketEvent, AreaEvent], **kwargs) -> None:
        """
        Broadcast all market and area events to the event_listener methods of the
        child dispatcher classes first (in order to propagate the event to the children of the
        area) and then to the Inter Area Agents of the children and this dispatcher's area.
        Strategy event methods (e.g. event_offer) should have precedence over MA's event methods.
        Reason for that is that the MA offer / bid  forwarding with MIN_BID/OFFER_AGE=0 setting
        enabled is expected to forward the offer / bid on the same tick that the offer is posted.
        If the MA event method is called before the strategy event method, then the offer / bid
        will not be forwarded on the same tick, but on the next one.
        For a similar reason (a market area should clear all offers and bids posted by its children
        before forwarding) the MA event method is called after all children event methods have
        been called.
        Args:
            event_type: Type of the event that will be broadcasted
            **kwargs: Arguments associated with the event

        Returns: None

        """
        if (not self.area.events.is_enabled and
                event_type not in [AreaEvent.ACTIVATE, AreaEvent.MARKET_CYCLE]):
            return

        # Broadcast to children in random order to ensure fairness
        for child in sorted(self.area.children, key=lambda _: random()):
            child.dispatcher.event_listener(event_type, **kwargs)

        # TODO: Enable the following block once GSYE-340 is implemented
        # if ConstSettings.ForwardMarketSettings.ENABLE_FORWARD_MARKETS:
        #     for forward_market_type in self._forward_agents:
        #         self._broadcast_notification_to_area_and_child_agents(
        #             forward_market_type, event_type, **kwargs)
        #     return

        market_id = kwargs.get("market_id")
        if not market_id and isinstance(event_type, MarketEvent):
            assert False, "MarketEvent should always provide a market_id."
        if (isinstance(event_type, AreaEvent)
                or self.area.is_market_spot(market_id)
                or self.area.is_market_balancing(market_id)):
            # Both spot and balancing agents need to be informed about each others events.
            # To be changed when updating the balancing market feature.
            self._broadcast_notification_to_area_and_child_agents(
                AvailableMarketTypes.SPOT, event_type, **kwargs)
            self._broadcast_notification_to_area_and_child_agents(
                AvailableMarketTypes.BALANCING, event_type, **kwargs)
        if isinstance(event_type, AreaEvent) or self.area.is_market_settlement(market_id):
            self._broadcast_notification_to_area_and_child_agents(
                AvailableMarketTypes.SETTLEMENT, event_type, **kwargs)
        if isinstance(event_type, AreaEvent) or self.area.is_market_future(market_id):
            self._broadcast_notification_to_area_and_child_agents(
                AvailableMarketTypes.FUTURE, event_type, **kwargs)

    def _should_dispatch_to_strategies(self, event_type: Union[AreaEvent, MarketEvent]) -> bool:
        if event_type is AreaEvent.ACTIVATE:
            return True
        return self.area.events.is_connected and self.area.events.is_enabled

    def event_listener(self, event_type: Union[MarketEvent, AreaEvent], **kwargs) -> None:
        """
        Listen to incoming events and forward them to either the strategy (for both market and
        area events), or the area object
        Args:
            event_type: Type of the event received by the listener
            **kwargs: Arguments of the event

        Returns: None

        """
        if event_type is AreaEvent.TICK and self._should_dispatch_to_strategies(event_type):
            self.area.tick_and_dispatch()
        if event_type is AreaEvent.MARKET_CYCLE:
            self.area.cycle_markets(_trigger_event=True)
        elif event_type is AreaEvent.ACTIVATE:
            self.area.activate(**kwargs)
        if self._should_dispatch_to_strategies(event_type):
            if self.area.strategy:
                self.area.strategy.event_listener(event_type, **kwargs)
        elif ((not self.area.events.is_enabled or not self.area.events.is_connected)
              and event_type == AreaEvent.MARKET_CYCLE and self.area.strategy is not None):
            self.area.strategy.event_on_disabled_area()

    @staticmethod
    def _create_agent_object(owner: "Area", higher_market: MarketBase,
                             lower_market: MarketBase, market_type: AvailableMarketTypes
                             ) -> Union[OneSidedAgent, SettlementAgent,
                                        BalancingAgent, FutureAgent]:
        agent_constructor_arguments = {
            "owner": owner,
            "higher_market": higher_market,
            "lower_market": lower_market,
            "min_offer_age": owner._min_offer_age
        }

        if market_type == AvailableMarketTypes.SPOT:
            if ConstSettings.MASettings.MARKET_TYPE == SpotMarketTypeEnum.ONE_SIDED.value:
                return OneSidedAgent(**agent_constructor_arguments)
            if ConstSettings.MASettings.MARKET_TYPE == SpotMarketTypeEnum.TWO_SIDED.value:
                return TwoSidedAgent(
                    **agent_constructor_arguments,
                    min_bid_age=owner._min_bid_age
                )
            raise WrongMarketTypeException("Wrong market type setting flag "
                                           f"{ConstSettings.MASettings.MARKET_TYPE}")
        if market_type == AvailableMarketTypes.SETTLEMENT:
            return SettlementAgent(**agent_constructor_arguments)
        if market_type == AvailableMarketTypes.BALANCING:
            return BalancingAgent(**agent_constructor_arguments)
        if market_type in [AvailableMarketTypes.FUTURE, *FORWARD_MARKET_TYPES]:
            return FutureAgent(**agent_constructor_arguments)

        assert False, f"Market type not supported {market_type}"

    @staticmethod
    def _get_agents_for_market_type(
            dispatcher_object, market_type: AvailableMarketTypes
    ) -> Dict[DateTime, Union[OneSidedAgent, BalancingAgent, SettlementAgent]]:
        if market_type == AvailableMarketTypes.SPOT:
            return dispatcher_object.spot_agents
        if market_type == AvailableMarketTypes.BALANCING:
            return dispatcher_object.balancing_agents
        if market_type == AvailableMarketTypes.SETTLEMENT:
            return dispatcher_object.settlement_agents
        assert False, f"Market type not supported {market_type}"

    @property
    def _should_agent_be_created(self) -> bool:
        if not self.area.parent:
            return False
        if self.area.strategy:
            return False
        if not self.area.parent.events.is_connected:
            return False
        if not self.area.children:
            return False
        return True

    def create_market_agents_for_forward_markets(
            self, market: MarketBase, market_type: AvailableMarketTypes
    ) -> None:
        """Create area agents for future markets; There should only be one per Area at any time."""
        if not self._should_agent_be_created:
            return
        if market_type not in self.area.parent.forward_markets:
            return
        higher_market = self.area.parent.forward_markets[market_type]

        market_agent = self._create_agent_object(
            owner=self.area,
            higher_market=higher_market,
            lower_market=market,
            market_type=market_type
        )
        self._forward_agents[market_type] = market_agent

    def create_market_agents_for_future_markets(self, market: MarketBase) -> None:
        """Create area agents for future markets; There should only be one per Area at any time."""
        if not self._should_agent_be_created:
            return

        market_agent = self._create_agent_object(
            owner=self.area,
            higher_market=self.area.parent.future_markets,
            lower_market=market,
            market_type=AvailableMarketTypes.FUTURE
        )

        self._future_agent = market_agent

    def create_market_agents(self, market_type: AvailableMarketTypes, market: MarketBase) -> None:
        """
        Create market agents for all market types, and store their reference to the respective
        dict.
        Args:
            market_type: Type of the market (spot/settlement/balancing/future)
            market: MarketBase object that will be associated with this market agent

        Returns: None

        """
        if not self._should_agent_be_created:
            return

        market_agents = self._get_agents_for_market_type(self, market_type)
        parent_markets = self.area.parent.get_market_instances_from_class_type(
            market_type)
        if market.time_slot in market_agents or market.time_slot not in parent_markets:
            return

        market_agent = self._create_agent_object(
            owner=self.area,
            higher_market=parent_markets[market.time_slot],
            lower_market=market,
            market_type=market_type
        )

        # Attach agent to own MA dict
        market_agents[market.time_slot] = market_agent

    def event_market_cycle(self) -> None:
        """Called every market cycle. Recycles old area agents."""
        self._delete_past_agents(self._spot_agents)
        self._delete_past_agents(self._balancing_agents)
        self._delete_past_agents(self._settlement_agents)
        if self._future_agent:
            self._future_agent.delete_engines()

    def _delete_past_agents(
            self, market_agent_member: Dict[DateTime, Union[
                OneSidedAgent, BalancingAgent, SettlementAgent]]) -> None:
        delete_agents = [(pm, agents_list) for pm, agents_list in market_agent_member.items() if
                         self.area.current_market and pm < self.area.current_market.time_slot]
        for pm, agent in delete_agents:
            if hasattr(agent, "engines"):
                agent.delete_engines()
                del agent.engines
            agent.higher_market = None
            agent.lower_market = None
            del market_agent_member[pm]


class RedisAreaDispatcher(AreaDispatcher):
    """
    Dispatch events to child areas using Redis instead of method calls like AreaDispatcher does.
    Should be used together with EVENT_DISPATCHING_VIA_REDIS parameter, and in modes where
    parts of the grid configuration are running on different machines.
    """
    def __init__(self, area: "Area",
                 redis_area: RedisCommunicator, redis_market: RedisCommunicator):
        super().__init__(area)
        self.area_event_dispatcher = RedisAreaEventDispatcher(area, self, redis_area)
        self.market_event_dispatcher = AreaRedisMarketEventDispatcher(area, self, redis_market)
        self.market_notify_event_dispatcher = MarketNotifyEventSubscriber(area, self)
        self.area_to_market_event_dispatcher = AreaToMarketEventPublisher(area)

    def publish_market_clearing(self) -> None:
        """Publish the market clearing result"""
        self.area_to_market_event_dispatcher.publish_markets_clearing()

    def broadcast_activate(self, **kwargs) -> None:
        """Broadcast activate event through Redis"""
        self.broadcast_notification(AreaEvent.ACTIVATE, **kwargs)

    def broadcast_tick(self, **kwargs) -> None:
        """Broadcast tick event through Redis"""
        self.broadcast_notification(AreaEvent.TICK, **kwargs)

    def broadcast_market_cycle(self, **kwargs) -> None:
        """Broadcast market cycle event through Redis"""
        self.market_notify_event_dispatcher.cycle_market_channels()
        self.broadcast_notification(AreaEvent.MARKET_CYCLE, **kwargs)

    def broadcast_balancing_market_cycle(self, **kwargs) -> None:
        """Broadcast balancing market cycle event through Redis"""
        self.broadcast_notification(AreaEvent.BALANCING_MARKET_CYCLE, **kwargs)

    def broadcast_notification(self, event_type: Union[AreaEvent, MarketEvent], **kwargs) -> None:
        """
        Broadcast notification of the event via Redis
        Args:
            event_type: Type of the event that will be broadcasted
            **kwargs: Arguments associated with the event

        Returns: None

        """
        if isinstance(event_type, AreaEvent):
            self.area_event_dispatcher.broadcast_event_redis(event_type, **kwargs)
        elif isinstance(event_type, MarketEvent):
            self.market_event_dispatcher.broadcast_event_redis(event_type, **kwargs)
        else:
            assert False, f"Event type {event_type} is not an Area or Market event."


class DispatcherFactory:
    """
    Factory class for constructing AreaDispatcher or RedisAreaDispatcher class according to
    configuration
    """
    def __init__(self, area: "Area"):
        self.event_dispatching_via_redis = \
            ConstSettings.GeneralSettings.EVENT_DISPATCHING_VIA_REDIS
        self.dispatcher = \
            RedisAreaDispatcher(area, RedisCommunicator(), RedisCommunicator()) \
            if self.event_dispatching_via_redis \
            else AreaDispatcher(area)

    def __call__(self) -> AreaDispatcher:
        return self.dispatcher
