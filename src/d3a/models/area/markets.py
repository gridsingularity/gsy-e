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
from collections import OrderedDict
from typing import Dict, List, TYPE_CHECKING

import d3a.constants
from d3a.d3a_core.util import is_timeslot_in_simulation_duration
from d3a.models.market import GridFee, Market
from d3a.models.market.balancing import BalancingMarket
from d3a.models.market.one_sided import OneSidedMarket
from d3a.models.market.two_sided import TwoSidedMarket
from d3a_interface.constants_limits import ConstSettings
from pendulum import DateTime

if TYPE_CHECKING:
    from d3a.models.area import Area


class AreaMarkets:
    """Class that holds all markets for areas."""

    def __init__(self, area_log):
        self.log = area_log
        # Children trade in `markets`
        self.markets = OrderedDict()  # type: Dict[DateTime, Market]
        self.balancing_markets = OrderedDict()  # type: Dict[DateTime, BalancingMarket]
        # Past markets
        self.past_markets = OrderedDict()  # type: Dict[DateTime, Market]
        self.past_balancing_markets = OrderedDict()  # type: Dict[DateTime, BalancingMarket]
        # Settlement markets
        self.settlement_markets = OrderedDict()  # type: Dict[DateTime, Market]
        self._indexed_future_markets = {}

    @property
    def indexed_future_markets(self) -> Dict:
        """Return dictionary that contains an id market mapping."""
        return self._indexed_future_markets

    @property
    def all_future_spot_markets(self) -> List:
        """Return all futur markets in a list."""
        return list(self.markets.values())

    @staticmethod
    def _is_it_time_to_delete_settlement_market(current_time: DateTime,
                                                time_slot: DateTime) -> bool:
        """Check if it is time to delete the settlement market with for the time_slot."""
        return (time_slot < current_time.subtract(
                    hours=ConstSettings.GeneralSettings.MAX_AGE_SETTLEMENT_MARKET_HOURS))

    def rotate_markets(self, current_time: DateTime) -> None:
        """Deal with market rotation of different types."""
        self._market_rotation(current_time=current_time)

        self._balancing_market_rotation(current_time=current_time)

        self._indexed_future_markets = {
            m.id: m for m in self.all_future_spot_markets
        }

    def _balancing_market_rotation(self, current_time: DateTime) -> None:
        """Move balancing markets to past."""
        if not ConstSettings.BalancingSettings.ENABLE_BALANCING_MARKET:
            return
        for time_slot in list(self.balancing_markets.keys()):
            print(current_time, time_slot)
            if time_slot < current_time:
                balancing_market = self.balancing_markets.pop(time_slot)

                self._move_to_past_markets(time_slot, balancing_market,
                                           self.past_balancing_markets)

    def _market_rotation(self, current_time: DateTime) -> None:
        """Move markets to past and rotate settlement markets."""

        for time_slot in list(self.markets.keys()):
            if time_slot < current_time:
                market = self.markets.pop(time_slot)
                if ConstSettings.GeneralSettings.ENABLE_SETTLEMENT_MARKETS:
                    self._rotate_settlement_markets(current_time)

                self._move_to_past_markets(time_slot, market, self.past_markets)

    def _move_to_past_markets(self, time_slot: DateTime,
                              market: Market, past_markets: Dict) -> None:
        """Move market to past markets (also used for balancing markets)."""
        market.readonly = True
        self._delete_past_markets(past_markets)
        past_markets[time_slot] = market
        self.log.error(
            f"Moving {past_markets[time_slot]} to past.")

    def _rotate_settlement_markets(self, current_time: DateTime) -> None:
        """create new settlement market, delete the oldest one"""
        delete_settlement_market_slots = [
            time_slot for time_slot in self.settlement_markets.keys()
            if self._is_it_time_to_delete_settlement_market(current_time=current_time,
                                                            time_slot=time_slot)]
        for time_slot in delete_settlement_market_slots:
            self.settlement_markets.pop(time_slot)

    def _delete_past_markets(self, past_markets: Dict):
        """Delete all past markets and connected instances."""
        if not d3a.constants.RETAIN_PAST_MARKET_STRATEGIES_STATE:
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
                del past_markets[pm]

    @staticmethod
    def _select_market_class(is_spot_market: bool) -> Market:
        """Select market class dependent on the global config."""
        if is_spot_market:
            if ConstSettings.IAASettings.MARKET_TYPE == 1:
                return OneSidedMarket
            elif ConstSettings.IAASettings.MARKET_TYPE == 2:
                return TwoSidedMarket
        else:
            return BalancingMarket

    def create_future_markets(self, current_time: DateTime,
                              is_spot_market: bool, area: "Area") -> bool:
        """Create future markets according to the market count."""
        markets = self.markets if is_spot_market else self.balancing_markets
        market_class = self._select_market_class(is_spot_market)

        changed = False
        for offset in (area.config.slot_length * i
                       for i in range(area.config.market_count)):
            time_slot = current_time + offset
            if time_slot not in markets:
                markets[time_slot] = self._create_market(market_class, time_slot, area,
                                                         is_spot_market)
                changed = True
                self.log.trace("Adding {t:{format}} market".format(
                    t=time_slot,
                    format="%H:%M" if area.config.slot_length.seconds > 60 else "%H:%M:%S"
                ))
        self._indexed_future_markets = {
            m.id: m for m in self.all_future_spot_markets
        }
        return changed

    def create_settlement_market(self, time_slot: DateTime, area: "Area") -> None:
        """Create a new settlement market."""
        new_settlement_market = \
            self._create_market(market_class=self._select_market_class(is_spot_market=True),
                                time_slot=time_slot,
                                area=area, is_spot_market=True)
        self.settlement_markets[time_slot] = new_settlement_market

    @staticmethod
    def _create_market(market_class: Market,
                       time_slot: DateTime, area: "Area", is_spot_market: bool) -> Market:
        """Create market for specific time_slot and market type."""
        market = market_class(
            time_slot=time_slot,
            bc=area.bc,
            notification_listener=area.dispatcher.broadcast_callback,
            grid_fee_type=area.config.grid_fee_type,
            grid_fees=GridFee(grid_fee_percentage=area.grid_fee_percentage,
                              grid_fee_const=area.grid_fee_constant),
            name=area.name,
            in_sim_duration=is_timeslot_in_simulation_duration(area.config, time_slot)
        )

        area.dispatcher.create_area_agents(is_spot_market, market)
        return market
