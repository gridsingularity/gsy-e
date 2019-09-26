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
import json
from numpy.random import random
from typing import Union
from logging import getLogger
from threading import Event
from redis import StrictRedis

from d3a.events.event_structures import MarketEvent, AreaEvent
from d3a.models.strategy.area_agents.one_sided_agent import OneSidedAgent
from d3a.models.strategy.area_agents.one_sided_alternative_pricing_agent import \
    OneSidedAlternativePricingAgent
from d3a.models.strategy.area_agents.two_sided_pay_as_bid_agent import TwoSidedPayAsBidAgent
from d3a.models.strategy.area_agents.two_sided_pay_as_clear_agent import TwoSidedPayAsClearAgent
from d3a.models.strategy.area_agents.balancing_agent import BalancingAgent
from d3a.models.appliance.inter_area import InterAreaAppliance
from d3a_interface.constants_limits import ConstSettings
from d3a.d3a_core.util import create_subdict_or_update
from d3a.d3a_core.redis_communication import REDIS_URL

log = getLogger(__name__)

EVENT_DISPATCHING_VIA_REDIS = ConstSettings.GeneralSettings.EVENT_DISPATCHING_VIA_REDIS


class AreaDispatcher:
    def __init__(self, area):
        self._inter_area_agents = {}  # type: Dict[DateTime, Dict[String, OneSidedAgent]]
        self._balancing_agents = {}  # type: Dict[DateTime, Dict[String, BalancingAgent]]
        self.area = area

    @property
    def interarea_agents(self):
        return self._inter_area_agents

    @property
    def balancing_agents(self):
        return self._balancing_agents

    def broadcast_activate(self, **kwargs):
        return self._broadcast_notification(AreaEvent.ACTIVATE, **kwargs)

    def broadcast_tick(self, **kwargs):
        return self._broadcast_notification(AreaEvent.TICK, **kwargs)

    def broadcast_market_cycle(self, **kwargs):
        return self._broadcast_notification(AreaEvent.MARKET_CYCLE, **kwargs)

    def broadcast_balancing_market_cycle(self, **kwargs):
        return self._broadcast_notification(AreaEvent.BALANCING_MARKET_CYCLE, **kwargs)

    @property
    def broadcast_callback(self):
        return self._broadcast_notification

    def _broadcast_notification(self, event_type: Union[MarketEvent, AreaEvent], **kwargs):
        if not self.area.events.is_enabled and \
           event_type not in [AreaEvent.ACTIVATE, AreaEvent.MARKET_CYCLE]:
            return
        # Broadcast to children in random order to ensure fairness
        for child in sorted(self.area.children, key=lambda _: random()):
            child.dispatcher.event_listener(event_type, **kwargs)
        # Also broadcast to IAAs. Again in random order
        for time_slot, agents in self._inter_area_agents.items():
            if time_slot not in self.area._markets.markets:
                # exclude past IAAs
                continue

            if not self.area.events.is_connected:
                break
            for area_name in sorted(agents, key=lambda _: random()):
                agents[area_name].event_listener(event_type, **kwargs)
        # Also broadcast to BAs. Again in random order
        # TODO: Refactor to reuse the spot market mechanism
        for time_slot, agents in self._balancing_agents.items():
            if time_slot not in self.area._markets.balancing_markets:
                # exclude past BAs
                continue

            if not self.area.events.is_connected:
                break
            for area_name in sorted(agents, key=lambda _: random()):
                agents[area_name].event_listener(event_type, **kwargs)

    def _should_dispatch_to_strategies_appliances(self, event_type):
        if event_type is AreaEvent.ACTIVATE:
            return True
        else:
            return self.area.events.is_connected and self.area.events.is_enabled

    def event_listener(self, event_type: Union[MarketEvent, AreaEvent], **kwargs):
        if event_type is AreaEvent.TICK:
            self.area.tick()
        if event_type is AreaEvent.MARKET_CYCLE:
            self.area._cycle_markets(_trigger_event=True)
        elif event_type is AreaEvent.ACTIVATE:
            self.area.activate()
        if self._should_dispatch_to_strategies_appliances(event_type):
            if self.area.strategy:
                self.area.strategy.event_listener(event_type, **kwargs)
            if self.area.appliance:
                self.area.appliance.event_listener(event_type, **kwargs)
        elif (not self.area.events.is_enabled or not self.area.events.is_connected) \
                and event_type == AreaEvent.MARKET_CYCLE:
            self.area.strategy.event_on_disabled_area()

    @staticmethod
    def select_agent_class(is_spot_market):
        if is_spot_market:
            if ConstSettings.IAASettings.MARKET_TYPE == 1:
                if ConstSettings.IAASettings.AlternativePricing.PRICING_SCHEME != 0:
                    return OneSidedAlternativePricingAgent
                else:
                    return OneSidedAgent
            elif ConstSettings.IAASettings.MARKET_TYPE == 2:
                return TwoSidedPayAsBidAgent
            elif ConstSettings.IAASettings.MARKET_TYPE == 3:
                return TwoSidedPayAsClearAgent
        else:
            return BalancingAgent

    def create_area_agents(self, is_spot_market, market):
        if not self.area.parent:
            return
        if self.area.strategy:
            return
        if not self.area.parent.events.is_connected:
            return

        agent_class = self.select_agent_class(is_spot_market)

        if is_spot_market:
            if market.time_slot in self.interarea_agents or \
                    market.time_slot not in self.area.parent._markets.markets:
                return
            # Only connect an InterAreaAgent if we have a parent, a corresponding
            # timeframe market exists in the parent and we have no strategy
            iaa = agent_class(
                owner=self.area,
                higher_market=self.area.parent._markets.markets[market.time_slot],
                lower_market=market,
                min_offer_age=ConstSettings.IAASettings.MIN_OFFER_AGE
            )

            self._delete_past_agents(self._inter_area_agents)
            self._delete_past_agents(self.area.parent.dispatcher._inter_area_agents)

            # Attach agent to own IAA list
            self._inter_area_agents = create_subdict_or_update(self._inter_area_agents,
                                                               market.time_slot,
                                                               {self.area.name: iaa})
            # And also to parents to allow events to flow from both markets
            self.area.parent.dispatcher._inter_area_agents = create_subdict_or_update(
                self.area.parent.dispatcher._inter_area_agents, market.time_slot,
                {self.area.name: iaa})

        else:
            if market.time_slot in self.balancing_agents or \
                    market.time_slot not in self.area.parent._markets.balancing_markets:
                return
            ba = agent_class(
                owner=self.area,
                higher_market=self.area.parent._markets.balancing_markets[market.time_slot],
                lower_market=market
            )

            self._balancing_agents = create_subdict_or_update(self._balancing_agents,
                                                              market.time_slot,
                                                              {self.area.name: ba})
            self.area.parent.dispatcher._balancing_agents = create_subdict_or_update(
                self.area.parent.dispatcher._balancing_agents, market.time_slot,
                {self.area.name: ba})

        if self.area.parent:
            # Add inter area appliance to report energy
            self.area.appliance = InterAreaAppliance(self.area.parent, self.area)

    def _delete_past_agents(self, area_agent_member):
        if not ConstSettings.GeneralSettings.KEEP_PAST_MARKETS:
            delete_agents = [pm for pm in area_agent_member.keys() if
                             self.area.current_market and pm < self.area.current_market.time_slot]
            for pm in delete_agents:
                for area_name in area_agent_member[pm]:
                    agent = area_agent_member[pm][area_name]
                    if hasattr(agent, "offers"):
                        del agent.offers
                    if hasattr(agent, "engines"):
                        for engine in agent.engines:
                            del engine.forwarded_offers
                            if hasattr(engine, "forwarded_bids"):
                                del engine.forwarded_bids
                        del agent.engines
                    agent.higher_market = None
                    agent.lower_market = None
                del area_agent_member[pm]


class RedisAreaDispatcher(AreaDispatcher):
    def __init__(self, area, redis_comm):
        super().__init__(area)
        self.redis_comm = redis_comm
        self.subscribe_to_response_channel()
        self.subscribe_to_area_event_channel()
        self.str_area_events = [event.name.lower() for event in AreaEvent]

    def subscribe_to_response_channel(self):
        channel = f"{self.area.slug}/area_event_response"
        self.redis_comm.sub_to_response(channel, self.response_callback)

    def subscribe_to_area_event_channel(self):
        channel = f"{self.area.slug}/area_event"
        self.redis_comm.sub_to_area_event(channel, self.event_listener_redis)

    def response_callback(self, payload):
        data = json.loads(payload["data"])
        if "response" in data:
            event_type = data["response"]
            if event_type in self.str_area_events:
                self.redis_comm.resume()
            else:
                raise Exception("RedisAreaDispatcher: Should never reach this point")

    def publish_event(self, area_slug, event_type: Union[MarketEvent, AreaEvent], **kwargs):
        send_data = {"event_type": event_type.value, "kwargs": kwargs}
        dispatch_chanel = f"{area_slug}/area_event"
        self.redis_comm.publish(dispatch_chanel, json.dumps(send_data))

    def _broadcast_event_redis(self, event_type: Union[MarketEvent, AreaEvent], **kwargs):
        if isinstance(event_type, AreaEvent):
            for child in sorted(self.area.children, key=lambda _: random()):
                self.publish_event(child.slug, event_type, **kwargs)
                self.redis_comm.wait()
        else:
            self._broadcast_notification(event_type=event_type, **kwargs)

    def event_listener_redis(self, payload):
        data = json.loads(payload["data"])
        kwargs = data["kwargs"]
        event_type = AreaEvent(data["event_type"])
        response_channel = f"{self.area.parent.slug}/area_event_response"
        response_data = json.dumps({"response": event_type.name.lower()})

        self.event_listener(event_type=event_type, **kwargs)

        self.redis_comm.publish(response_channel, response_data)

    def broadcast_activate(self, **kwargs):
        self._broadcast_event_redis(AreaEvent.ACTIVATE, **kwargs)

    def broadcast_tick(self, **kwargs):
        return self._broadcast_event_redis(AreaEvent.TICK, **kwargs)

    def broadcast_market_cycle(self, **kwargs):
        return self._broadcast_event_redis(AreaEvent.MARKET_CYCLE, **kwargs)

    def broadcast_balancing_market_cycle(self, **kwargs):
        return self._broadcast_event_redis(AreaEvent.BALANCING_MARKET_CYCLE, **kwargs)


class RedisAreaCommunicator:
    def __init__(self):
        self.redis_db = StrictRedis.from_url(REDIS_URL)
        self.pubsub = self.redis_db.pubsub()
        self.pubsub_response = self.redis_db.pubsub()
        self.area_event = Event()

    def publish(self, channel, data):
        self.redis_db.publish(channel, data)

    def wait(self):
        self.area_event.wait()
        self.area_event.clear()

    def resume(self):
        self.area_event.set()

    def sub_to_response(self, channel, callback):
        self.pubsub_response.subscribe(**{channel: callback})
        self.pubsub_response.run_in_thread(daemon=True)

    def sub_to_area_event(self, channel, callback):
        self.pubsub.subscribe(**{channel: callback})
        self.pubsub.run_in_thread(daemon=True)


class DispatcherFactory:
    def __init__(self, area):
        self.event_dispatching_via_redis = \
            ConstSettings.GeneralSettings.EVENT_DISPATCHING_VIA_REDIS
        self.dispatcher = RedisAreaDispatcher(area, RedisAreaCommunicator()) \
            if self.event_dispatching_via_redis else AreaDispatcher(area)

    def __call__(self):
        return self.dispatcher
