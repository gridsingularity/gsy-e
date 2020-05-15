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
from pendulum import DateTime # noqa
from typing import Dict  # noqa

from d3a.models.market import TransferFees
from d3a.models.market.two_sided_pay_as_bid import TwoSidedPayAsBid
from d3a.models.market.two_sided_pay_as_clear import TwoSidedPayAsClear
from d3a.models.market.one_sided import OneSidedMarket
from d3a.models.market.balancing import BalancingMarket
from d3a.models.market import Market # noqa
from d3a_interface.constants_limits import ConstSettings
from collections import OrderedDict
from d3a.d3a_core.util import is_timeslot_in_simulation_duration


class AreaMarkets:
    def __init__(self, area_log):
        # Children trade in `markets`
        self.log = area_log
        self.markets = OrderedDict()  # type: Dict[DateTime, Market]
        self.balancing_markets = OrderedDict()  # type: Dict[DateTime, BalancingMarket]
        # Past markets
        self.past_markets = OrderedDict()  # type: Dict[DateTime, Market]
        self.past_balancing_markets = OrderedDict()  # type: Dict[DateTime, BalancingMarket]
        self._indexed_future_markets = {}

    @property
    def indexed_future_markets(self):
        return self._indexed_future_markets

    @property
    def all_spot_markets(self):
        return list(self.markets.values()) + list(self.past_markets.values())

    @property
    def all_future_spot_markets(self):
        return list(self.markets.values())

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
        self._indexed_future_markets = {
            m.id: m for m in self.all_future_spot_markets
        }

    def _market_rotation(self, current_time, markets, past_markets, area_agent):
        for timeframe in list(markets.keys()):
            if timeframe < current_time:
                market = markets.pop(timeframe)
                market.readonly = True
                self._delete_past_markets(past_markets, timeframe)
                past_markets[timeframe] = market
                self.log.trace("Moving {t:%H:%M} {m} to past"
                               .format(t=timeframe, m=past_markets[timeframe].name))

    def _delete_past_markets(self, past_markets, timeframe):
        if not ConstSettings.GeneralSettings.KEEP_PAST_MARKETS:
            delete_markets = [pm for pm in past_markets if
                              pm not in self.markets.values()]
            for pm in delete_markets:
                if ConstSettings.GeneralSettings.EVENT_DISPATCHING_VIA_REDIS:
                    past_markets[pm].redis_api.stop()
                del past_markets[pm].offers
                del past_markets[pm].trades
                del past_markets[pm].offer_history
                del past_markets[pm].notification_listeners
                del past_markets[pm].bids
                del past_markets[pm].bid_history
                del past_markets[pm].traded_energy
                del past_markets[pm].accumulated_actual_energy_agg
                del past_markets[pm]

    @staticmethod
    def select_market_class(is_spot_market):
        if is_spot_market:
            if ConstSettings.IAASettings.MARKET_TYPE == 1:
                return OneSidedMarket
            elif ConstSettings.IAASettings.MARKET_TYPE == 2:
                return TwoSidedPayAsBid
            elif ConstSettings.IAASettings.MARKET_TYPE == 3:
                return TwoSidedPayAsClear
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
                    time_slot=timeframe,
                    bc=area.bc,
                    notification_listener=area.dispatcher.broadcast_callback,
                    grid_fee_type=area.config.grid_fee_type,
                    transfer_fees=TransferFees(grid_fee_percentage=area.grid_fee_percentage,
                                               transfer_fee_const=area.transfer_fee_const),
                    name=area.name,
                    in_sim_duration=is_timeslot_in_simulation_duration(area.config, timeframe)
                )

                area.dispatcher.create_area_agents(is_spot_market, market)
                markets[timeframe] = market
                changed = True
                self.log.trace("Adding {t:{format}} market".format(
                    t=timeframe,
                    format="%H:%M"
                           if area.config.slot_length.total_seconds() > 60
                    else "%H:%M:%S"
                ))
        self._indexed_future_markets = {
            m.id: m for m in self.all_future_spot_markets
        }
        return changed
