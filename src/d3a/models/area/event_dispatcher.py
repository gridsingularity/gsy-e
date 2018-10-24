from random import random
from typing import Union
from collections import defaultdict
from d3a.models.events import MarketEvent, AreaEvent


class AreaDispatcher:
    def __init__(self, area):
        self.listeners = []
        self._inter_area_agents = \
            defaultdict(list)  # type: Dict[DateTime, List[InterAreaAgent]]
        self._balancing_agents = \
            defaultdict(list)  # type: Dict[DateTime, List[BalancingAgent]]
        self.area = area

    @property
    def interarea_agents(self):
        return self._inter_area_agents

    @property
    def balancing_agents(self):
        return self._balancing_agents

    def broadcast_activate(self, **kwargs):
        return self._broadcast_notification(AreaEvent.ACTIVATE, **kwargs)

    def broadcast_tick(self, area, **kwargs):
        return self._broadcast_notification(AreaEvent.TICK, area=area, **kwargs)

    def broadcast_market_cycle(self, **kwargs):
        return self._broadcast_notification(AreaEvent.MARKET_CYCLE, **kwargs)

    def broadcast_balancing_market_cycle(self, **kwargs):
        return self._broadcast_notification(AreaEvent.BALANCING_MARKET_CYCLE, **kwargs)

    @property
    def broadcast_callback(self):
        return self._broadcast_notification

    def _broadcast_notification(self, event_type: Union[MarketEvent, AreaEvent], **kwargs):
        # Broadcast to children in random order to ensure fairness
        for child in sorted(self.area.children, key=lambda _: random()):
            child.dispatcher.event_listener(event_type, **kwargs)
        # Also broadcast to IAAs. Again in random order
        for time_slot, agents in self._inter_area_agents.items():
            if time_slot not in self.area._markets.markets:
                # exclude past IAAs
                continue

            for agent in sorted(agents, key=lambda _: random()):
                agent.event_listener(event_type, **kwargs)
        # Also broadcast to BAs. Again in random order
        for time_slot, agents in self._balancing_agents.items():
            if time_slot not in self.area._markets.balancing_markets:
                # exclude past BAs
                continue

            for agent in sorted(agents, key=lambda _: random()):
                agent.event_listener(event_type, **kwargs)
        for listener in self.listeners:
            listener.event_listener(event_type, **kwargs)

    def add_listener(self, listener):
        self.listeners.append(listener)

    def event_listener(self, event_type: Union[MarketEvent, AreaEvent], **kwargs):
        if event_type is AreaEvent.TICK:
            self.area.tick()
        # TODO: Review this change. Make sure this trigger is not needed anywhere else
        # elif event_type is AreaEvent.MARKET_CYCLE:
        #     self._cycle_markets(_market_cycle=True)
        elif event_type is AreaEvent.ACTIVATE:
            self.area.activate()
        if self.area.strategy:
            self.area.strategy.event_listener(event_type, **kwargs)
        if self.area.appliance:
            self.area.appliance.event_listener(event_type, **kwargs)
