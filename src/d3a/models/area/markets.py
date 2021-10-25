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
from typing import Dict, TYPE_CHECKING

from d3a_interface.constants_limits import ConstSettings
from d3a_interface.enums import SpotMarketTypeEnum
from pendulum import DateTime

from d3a.d3a_core.util import is_time_slot_in_simulation_duration
from d3a.models.area.market_rotators import (BaseRotator, DefaultMarketRotator,
                                             SettlementMarketRotator, FutureMarketRotator)
from d3a.models.market import GridFee, Market
from d3a.models.market.balancing import BalancingMarket
from d3a.models.market.future import FutureMarkets
from d3a.models.market.market_structures import AvailableMarketTypes
from d3a.models.market.one_sided import OneSidedMarket
from d3a.models.market.settlement import SettlementMarket
from d3a.models.market.two_sided import TwoSidedMarket

if TYPE_CHECKING:
    from d3a.models.area import Area


class AreaMarkets:
    """Class that holds all markets for areas."""

    def __init__(self, area_log):
        self.log = area_log
        # Children trade in `markets`
        self.markets:  Dict[DateTime, Market] = OrderedDict()
        self.balancing_markets:  Dict[DateTime, BalancingMarket] = OrderedDict()
        self.settlement_markets: Dict[DateTime, TwoSidedMarket] = OrderedDict()
        # Past markets:
        self.past_markets:  Dict[DateTime, Market] = OrderedDict()
        self.past_balancing_markets:  Dict[DateTime, BalancingMarket] = OrderedDict()
        self.past_settlement_markets: Dict[DateTime, TwoSidedMarket] = OrderedDict()
        # TODO: rename and refactor:
        self.indexed_future_markets = {}
        # Future markets:
        self.future_markets = None

        self.spot_market_rotator = BaseRotator()
        self.balancing_market_rotator = BaseRotator()
        self.settlement_market_rotator = BaseRotator()
        self.future_market_rotator = BaseRotator()

    def activate_future_markets(self, area: "Area") -> None:
        self.future_markets = FutureMarkets(
            bc=area.bc,
            notification_listener=area.dispatcher.broadcast_callback,
            grid_fee_type=area.config.grid_fee_type,
            grid_fees=GridFee(grid_fee_percentage=area.grid_fee_percentage,
                              grid_fee_const=area.grid_fee_constant),
            name=area.name)

    def activate_market_rotators(self):
        """The user specific ConstSettings are not available when the class is constructed,
        so we need to have a two-stage initialization here."""
        self.spot_market_rotator = DefaultMarketRotator(self.markets, self.past_markets)
        if ConstSettings.BalancingSettings.ENABLE_BALANCING_MARKET:
            self.balancing_market_rotator = (
                DefaultMarketRotator(self.balancing_markets, self.past_balancing_markets))
        if ConstSettings.SettlementMarketSettings.ENABLE_SETTLEMENT_MARKETS:
            self.settlement_market_rotator = (
                SettlementMarketRotator(self.settlement_markets, self.past_settlement_markets))
        if self.future_markets:
            self.future_market_rotator = FutureMarketRotator(self.future_markets)

    def _update_indexed_future_markets(self) -> None:
        """Update the indexed_future_markets mapping."""
        self.indexed_future_markets = {m.id: m for m in self.markets.values()}

    def rotate_markets(self, current_time: DateTime) -> None:
        """Deal with market rotation of different types."""
        self.spot_market_rotator.rotate(current_time)
        self.balancing_market_rotator.rotate(current_time)
        self.settlement_market_rotator.rotate(current_time)
        self.future_market_rotator.rotate(current_time)

        self._update_indexed_future_markets()

    @staticmethod
    def _select_market_class(market_type: AvailableMarketTypes) -> Market:
        """Select market class dependent on the global config."""
        if market_type == AvailableMarketTypes.SPOT:
            if ConstSettings.IAASettings.MARKET_TYPE == SpotMarketTypeEnum.ONE_SIDED.value:
                return OneSidedMarket
            elif ConstSettings.IAASettings.MARKET_TYPE == SpotMarketTypeEnum.TWO_SIDED.value:
                return TwoSidedMarket
        elif market_type == AvailableMarketTypes.SETTLEMENT:
            return SettlementMarket
        elif market_type == AvailableMarketTypes.BALANCING:
            return BalancingMarket
        else:
            assert False, f"Market type not supported {market_type}"

    def get_market_instances_from_class_type(self, market_type: AvailableMarketTypes) -> Dict:
        """Select market dict based on the market class type."""
        if market_type == AvailableMarketTypes.SPOT:
            return self.markets
        elif market_type == AvailableMarketTypes.SETTLEMENT:
            return self.settlement_markets
        elif market_type == AvailableMarketTypes.BALANCING:
            return self.balancing_markets
        else:
            assert False, f"Market type not supported {market_type}"

    def create_new_spot_market(self, current_time: DateTime,
                               market_type: AvailableMarketTypes, area: "Area") -> bool:
        """Create future markets according to the market count."""
        markets = self.get_market_instances_from_class_type(market_type)
        market_class = self._select_market_class(market_type)

        changed = False
        if not markets or current_time not in markets:
            markets[current_time] = self._create_market(
                market_class, current_time, area, market_type)
            changed = True
            self.log.trace("Adding {t:{format}} market".format(
                t=current_time,
                format="%H:%M" if area.config.slot_length.seconds > 60 else "%H:%M:%S"
            ))
        self._update_indexed_future_markets()
        return changed

    def create_settlement_market(self, time_slot: DateTime, area: "Area") -> None:
        """Create a new settlement market."""
        self.settlement_markets[time_slot] = (
            self._create_market(market_class=SettlementMarket,
                                time_slot=time_slot,
                                area=area, market_type=AvailableMarketTypes.SETTLEMENT))
        self.log.trace(
            "Adding Settlement {t:{format}} market".format(
                t=time_slot,
                format="%H:%M" if area.config.slot_length.seconds > 60 else "%H:%M:%S"))

    @staticmethod
    def _create_market(market_class: Market,
                       time_slot: DateTime, area: "Area",
                       market_type: AvailableMarketTypes) -> Market:
        """Create market for specific time_slot and market type."""
        market = market_class(
            time_slot=time_slot,
            bc=area.bc,
            notification_listener=area.dispatcher.broadcast_notification,
            grid_fee_type=area.config.grid_fee_type,
            grid_fees=GridFee(grid_fee_percentage=area.grid_fee_percentage,
                              grid_fee_const=area.grid_fee_constant),
            name=area.name,
            in_sim_duration=is_time_slot_in_simulation_duration(area.config, time_slot)
        )

        area.dispatcher.create_area_agents(market_type, market)
        return market
