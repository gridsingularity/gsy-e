from random import random
from typing import Union
from collections import defaultdict
from d3a.events.event_structures import MarketEvent, AreaEvent
from d3a.models.strategy.area_agents.one_sided_agent import OneSidedAgent
from d3a.models.strategy.area_agents.two_sided_pay_as_bid_agent import TwoSidedPayAsBidAgent
from d3a.models.strategy.area_agents.two_sided_pay_as_clear_agent import TwoSidedPayAsClearAgent
from d3a.models.strategy.area_agents.balancing_agent import BalancingAgent
from d3a.models.appliance.inter_area import InterAreaAppliance
from d3a.models.const import ConstSettings


class AreaDispatcher:
    def __init__(self, area):
        self.listeners = []
        self._inter_area_agents = \
            defaultdict(list)  # type: Dict[DateTime, List[OneSidedAgent]]
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
        elif event_type is AreaEvent.ACTIVATE:
            self.area.activate()
        if self.area.strategy:
            self.area.strategy.event_listener(event_type, **kwargs)
        if self.area.appliance:
            self.area.appliance.event_listener(event_type, **kwargs)

    @staticmethod
    def select_agent_class(is_spot_market):
        if is_spot_market:
            if ConstSettings.IAASettings.MARKET_TYPE == 1:
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
                transfer_fee_pct=self.area.config.iaa_fee
            )
            # Attach agent to own IAA list
            self.interarea_agents[market.time_slot].append(iaa)
            # And also to parents to allow events to flow form both markets
            self.area.parent.dispatcher.interarea_agents[market.time_slot].append(iaa)
        else:
            if market.time_slot in self.balancing_agents or \
                    market.time_slot not in self.area.parent._markets.balancing_markets:
                return
            ba = agent_class(
                owner=self.area,
                higher_market=self.area.parent._markets.balancing_markets[market.time_slot],
                lower_market=market,
                transfer_fee_pct=self.area.config.iaa_fee
            )
            self.balancing_agents[market.time_slot].append(ba)
            self.area.parent.dispatcher.balancing_agents[market.time_slot].append(ba)

        if self.area.parent:
            # Add inter area appliance to report energy
            self.area.appliance = InterAreaAppliance(self.area.parent, self.area)
