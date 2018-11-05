from pendulum import DateTime # noqa
from typing import Dict  # noqa

from d3a.models.market.two_sided_pay_as_bid import TwoSidedPayAsBid
from d3a.models.market.one_sided import OneSidedMarket
from d3a.models.market.balancing import BalancingMarket
from d3a.models.market import Market # noqa
from d3a.models.const import ConstSettings
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

    @staticmethod
    def select_market_class(is_spot_market):
        if is_spot_market:
            if ConstSettings.IAASettings.MARKET_TYPE == 1:
                return OneSidedMarket
            else:
                return TwoSidedPayAsBid
        else:
            return BalancingMarket

    def create_future_markets(self, current_time, is_spot_market, area):
        markets = self.markets if is_spot_market else self.balancing_markets
        market_class = self.select_market_class(is_spot_market)

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
