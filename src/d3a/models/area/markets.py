from d3a.models.market import Market, BalancingMarket
from d3a.models.appliance.inter_area import InterAreaAppliance
from collections import OrderedDict
# TODO remove IAA and BA from here to the dispatcher
from d3a.models.strategy.inter_area import InterAreaAgent, BalancingAgent


class AreaMarkets:
    def __init__(self, area):
        # Children trade in `markets`
        self._area = area
        self.markets = OrderedDict()  # type: Dict[DateTime, Market]
        self.balancing_markets = OrderedDict()  # type: Dict[DateTime, BalancingMarket]
        # Past markets
        self.past_markets = OrderedDict()  # type: Dict[DateTime, Market]
        self.past_balancing_markets = OrderedDict()  # type: Dict[DateTime, BalancingMarket]

    def rotate_markets(self, current_time, stats):
        # Move old and current markets & balancing_markets to
        # `past_markets` & past_balancing_markets. We use `list()` here to get a copy since we
        # modify the market list in-place
        self._market_rotation(current_time=current_time, markets=self.markets,
                              past_markets=self.past_markets,
                              area_agent=self._area.dispatcher.interarea_agents)
        if self.balancing_markets is not None:
            self._market_rotation(current_time=current_time, markets=self.balancing_markets,
                                  past_markets=self.past_balancing_markets,
                                  area_agent=self._area.dispatcher.balancing_agents)
        stats.update_accumulated(self.past_markets)

    @property
    def market_with_most_expensive_offer(self):
        # In case of a tie, max returns the first market occurrence in order to
        # satisfy the most recent market slot
        return max(self.markets.values(),
                   key=lambda m: m.sorted_offers[0].price / m.sorted_offers[0].energy)

    def _market_rotation(self, current_time, markets, past_markets, area_agent):
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
                self._area.log.debug("Moving {t:%H:%M} {m} to past"
                                     .format(t=timeframe, m=past_markets[timeframe].area.name))

    def _create_future_markets(self, current_time, markets, parent, parent_markets,
                               area_agent, parent_area_agent, agent_class, market_class):
        changed = False
        for offset in (self._area.config.slot_length * i
                       for i in range(self._area.config.market_count)):
            timeframe = current_time + offset
            if timeframe not in markets:
                # Create markets for missing slots
                market = market_class(
                    timeframe, self._area,
                    notification_listener=self._area.dispatcher.broadcast_callback
                )
                if market not in area_agent:
                    if parent and timeframe in parent_markets and not self._area.strategy:
                        # Only connect an InterAreaAgent if we have a parent, a corresponding
                        # timeframe market exists in the parent and we have no strategy
                        iaa = agent_class(
                            owner=self._area,
                            higher_market=parent_markets[timeframe],
                            lower_market=market,
                            transfer_fee_pct=self._area.config.iaa_fee
                        )
                        # Attach agent to own IAA list
                        area_agent[timeframe].append(iaa)
                        # And also to parents to allow events to flow form both markets
                        parent_area_agent[timeframe].append(iaa)
                        if parent:
                            # Add inter area appliance to report energy
                            self.appliance = InterAreaAppliance(parent, self._area)
                markets[timeframe] = market
                changed = True
                self._area.log.debug("Adding {t:{format}} market".format(
                    t=timeframe,
                    format="%H:%M"
                           if self._area.config.slot_length.total_seconds() > 60
                    else "%H:%M:%S"
                ))
        return changed

    def create_spot_markets(self, now, parent, dispatcher):
        return self._create_future_markets(
            current_time=now, markets=self.markets,
            parent=parent,
            parent_markets=parent._markets.markets
            if parent is not None else None,
            area_agent=dispatcher.interarea_agents,
            parent_area_agent=parent.dispatcher.interarea_agents
            if parent is not None else None,
            agent_class=InterAreaAgent,
            market_class=Market
        )

    def create_balancing_markets(self, now, parent, dispatcher):
        return self._create_future_markets(
            current_time=now, markets=self.balancing_markets,
            parent=parent,
            parent_markets=parent._markets.balancing_markets
            if parent is not None else None,
            area_agent=dispatcher.balancing_agents,
            parent_area_agent=parent.dispatcher.balancing_agents
            if parent is not None else None,
            agent_class=BalancingAgent,
            market_class=BalancingMarket
        )
