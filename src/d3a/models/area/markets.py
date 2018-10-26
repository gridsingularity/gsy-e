from d3a.models.market import Market, BalancingMarket
from collections import OrderedDict


class AreaMarkets:
    def __init__(self, area_log):
        # Children trade in `markets`
        self.log = area_log
        self.markets = OrderedDict()  # type: Dict[DateTime, Market]
        self.balancing_markets = OrderedDict()  # type: Dict[DateTime, BalancingMarket]
        # Past markets
        self.past_markets = OrderedDict()  # type: Dict[DateTime, Market]
        self.past_balancing_markets = OrderedDict()  # type: Dict[DateTime, BalancingMarket]

    @property
    def all_spot_markets(self):
        return list(self.markets.values()) + list(self.past_markets.values())

    def rotate_markets(self, current_time, stats, dispatcher):
        # Move old and current markets & balancing_markets to
        # `past_markets` & past_balancing_markets. We use `list()` here to get a copy since we
        # modify the market list in-place
        self._market_rotation(current_time=current_time, markets=self.markets,
                              past_markets=self.past_markets,
                              area_agent=dispatcher.interarea_agents)
        if self.balancing_markets is not None:
            self._market_rotation(current_time=current_time, markets=self.balancing_markets,
                                  past_markets=self.past_balancing_markets,
                                  area_agent=dispatcher.balancing_agents)
        stats.update_accumulated()

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
                self.log.debug("Moving {t:%H:%M} {m} to past"
                               .format(t=timeframe, m=past_markets[timeframe].area.name))

    def create_future_markets(self, current_time, is_spot_market, area):
        markets = self.markets if is_spot_market else self.balancing_markets
        market_class = Market if is_spot_market else BalancingMarket

        changed = False
        for offset in (area.config.slot_length * i
                       for i in range(area.config.market_count)):
            timeframe = current_time + offset
            if timeframe not in markets:
                # Create markets for missing slots
                market = market_class(
                    timeframe, area,
                    notification_listener=area.dispatcher.broadcast_callback
                )

                area.dispatcher.create_area_agents(is_spot_market, market)
                markets[timeframe] = market
                changed = True
                self.log.debug("Adding {t:{format}} market".format(
                    t=timeframe,
                    format="%H:%M"
                           if area.config.slot_length.total_seconds() > 60
                    else "%H:%M:%S"
                ))
        return changed
