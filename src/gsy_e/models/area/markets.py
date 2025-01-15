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

from collections import OrderedDict
from typing import Dict, TYPE_CHECKING, Optional, List

from gsy_framework.constants_limits import ConstSettings, TIME_FORMAT
from gsy_framework.enums import AvailableMarketTypes
from gsy_framework.utils import is_time_slot_in_simulation_duration
from pendulum import DateTime

from gsy_e.gsy_e_core.enums import FORWARD_MARKET_TYPES
from gsy_e.gsy_e_core.util import is_one_sided_market_simulation, is_two_sided_market_simulation
from gsy_e.models.area.market_rotators import (
    BaseRotator,
    DefaultMarketRotator,
    SettlementMarketRotator,
    FutureMarketRotator,
    ForwardMarketRotatorBase,
    DayForwardMarketRotator,
    WeekForwardMarketRotator,
    MonthForwardMarketRotator,
    YearForwardMarketRotator,
    IntradayMarketRotator,
)
from gsy_e.models.market import GridFee, MarketBase
from gsy_e.models.market.balancing import BalancingMarket
from gsy_e.models.market.forward import (
    ForwardMarketBase,
    DayForwardMarket,
    WeekForwardMarket,
    MonthForwardMarket,
    YearForwardMarket,
    IntradayMarket,
)
from gsy_e.models.market.future import FutureMarkets
from gsy_e.models.market.one_sided import OneSidedMarket
from gsy_e.models.market.settlement import SettlementMarket
from gsy_e.models.market.two_sided import TwoSidedMarket

if TYPE_CHECKING:
    from gsy_e.models.area import Area

_FORWARD_MARKET_TYPE_MAPPING = {
    AvailableMarketTypes.DAY_FORWARD: DayForwardMarket,
    AvailableMarketTypes.WEEK_FORWARD: WeekForwardMarket,
    AvailableMarketTypes.MONTH_FORWARD: MonthForwardMarket,
    AvailableMarketTypes.YEAR_FORWARD: YearForwardMarket,
    AvailableMarketTypes.INTRADAY: IntradayMarket,
}

_FORWARD_MARKET_ROTATOR_MAPPING = {
    AvailableMarketTypes.DAY_FORWARD: DayForwardMarketRotator,
    AvailableMarketTypes.WEEK_FORWARD: WeekForwardMarketRotator,
    AvailableMarketTypes.MONTH_FORWARD: MonthForwardMarketRotator,
    AvailableMarketTypes.YEAR_FORWARD: YearForwardMarketRotator,
    AvailableMarketTypes.INTRADAY: IntradayMarketRotator,
}


class AreaMarkets:
    """Class that holds all markets for areas."""

    # pylint: disable = too-many-instance-attributes

    def __init__(self, area_log):
        self.log = area_log
        # Children trade in `markets`
        self.markets: Dict[DateTime, MarketBase] = OrderedDict()
        self.balancing_markets: Dict[DateTime, BalancingMarket] = OrderedDict()
        self.settlement_markets: Dict[DateTime, TwoSidedMarket] = OrderedDict()
        # Past markets:
        self.past_markets: Dict[DateTime, MarketBase] = OrderedDict()
        self.past_balancing_markets: Dict[DateTime, BalancingMarket] = OrderedDict()
        self.past_settlement_markets: Dict[DateTime, TwoSidedMarket] = OrderedDict()
        # TODO: rename and refactor in the frame of D3ASIM-3633:
        self.indexed_future_markets = {}
        # Future markets:
        self.future_markets: Optional[FutureMarkets] = None
        self.forward_markets: Optional[Dict[AvailableMarketTypes, ForwardMarketBase]] = {}

        self._spot_market_rotator = BaseRotator()
        self._balancing_market_rotator = BaseRotator()
        self._settlement_market_rotator = BaseRotator()
        self._future_market_rotator = BaseRotator()
        self._forward_market_rotators: Optional[
            Dict[AvailableMarketTypes, ForwardMarketRotatorBase]
        ] = {}

        self.spot_market_ids: List = []
        self.balancing_market_ids: List = []
        self.settlement_market_ids: List = []

    def update_area_market_id_lists(self) -> None:
        """Populate lists of market-ids that are currently in the market dicts."""
        self.spot_market_ids: List = [market.id for market in self.markets.values()]
        self.balancing_market_ids: List = [market.id for market in self.balancing_markets.values()]
        self.settlement_market_ids: List = [
            market.id for market in self.settlement_markets.values()
        ]

    def activate_future_markets(self, area: "Area") -> None:
        """Wrapper for activation methods for all future market types."""
        self._activate_forward_markets(area)
        self._activate_future_markets(area)

    def _activate_future_markets(self, area: "Area") -> None:
        """
        Create FutureMarkets instance and create MAs that communicate to the parent FutureMarkets.
        """
        market = FutureMarkets(
            bc=area.bc,
            notification_listener=area.dispatcher.broadcast_notification,
            grid_fee_type=area.config.grid_fee_type,
            grid_fees=GridFee(
                grid_fee_percentage=area.grid_fee_percentage, grid_fee_const=area.grid_fee_constant
            ),
            name=area.name,
        )
        self.future_markets = market
        self.future_markets.update_clock(area.now)
        area.dispatcher.create_market_agents_for_future_markets(market)

    def _activate_forward_markets(self, area: "Area") -> None:
        """
        Create forward market instances and create MAs that communicate to the parent
        forward market.
        """
        if not ConstSettings.ForwardMarketSettings.ENABLE_FORWARD_MARKETS:
            return

        for market_type, market_class in _FORWARD_MARKET_TYPE_MAPPING.items():
            market = market_class(
                bc=area.bc,
                notification_listener=area.dispatcher.broadcast_notification,
                grid_fee_type=area.config.grid_fee_type,
                grid_fees=GridFee(
                    grid_fee_percentage=area.grid_fee_percentage,
                    grid_fee_const=area.grid_fee_constant,
                ),
                name=area.name,
            )
            self.forward_markets[market_type] = market
            self.forward_markets[market_type].update_clock(area.now)
            area.dispatcher.create_market_agents_for_forward_markets(market, market_type)

    def activate_market_rotators(self):
        """The user specific ConstSettings are not available when the class is constructed,
        so we need to have a two-stage initialization here."""
        self._spot_market_rotator = DefaultMarketRotator(self.markets, self.past_markets)
        if ConstSettings.BalancingSettings.ENABLE_BALANCING_MARKET:
            self._balancing_market_rotator = DefaultMarketRotator(
                self.balancing_markets, self.past_balancing_markets
            )
        if ConstSettings.SettlementMarketSettings.ENABLE_SETTLEMENT_MARKETS:
            self._settlement_market_rotator = SettlementMarketRotator(
                self.settlement_markets, self.past_settlement_markets
            )
        if self.future_markets:
            self._future_market_rotator = FutureMarketRotator(self.future_markets)
        if self.forward_markets:
            for market_type, rotator_class in _FORWARD_MARKET_ROTATOR_MAPPING.items():
                self._forward_market_rotators[market_type] = rotator_class(
                    self.forward_markets[market_type]
                )

    def _update_indexed_future_markets(self) -> None:
        """Update the indexed_future_markets mapping."""
        self.indexed_future_markets = {m.id: m for m in self.markets.values()}

    def _rotate_forward_markets(self, current_time: DateTime) -> None:
        for rotator in self._forward_market_rotators.values():
            rotator.rotate(current_time)

    def rotate_markets(self, current_time: DateTime) -> None:
        """Deal with market rotation of different types."""
        self._spot_market_rotator.rotate(current_time)
        self._balancing_market_rotator.rotate(current_time)
        self._settlement_market_rotator.rotate(current_time)
        self._future_market_rotator.rotate(current_time)

        if ConstSettings.ForwardMarketSettings.ENABLE_FORWARD_MARKETS:
            self._rotate_forward_markets(current_time)

        self._update_indexed_future_markets()

    @staticmethod
    def _select_market_class(market_type: AvailableMarketTypes) -> type(MarketBase):
        """Select market class dependent on the global config."""
        if market_type == AvailableMarketTypes.SPOT:
            if is_one_sided_market_simulation():
                return OneSidedMarket
            if is_two_sided_market_simulation():
                return TwoSidedMarket
        if market_type == AvailableMarketTypes.SETTLEMENT:
            return SettlementMarket
        if market_type == AvailableMarketTypes.BALANCING:
            return BalancingMarket

        assert False, f"Market type not supported {market_type}"

    def get_market_instances_from_class_type(self, market_type: AvailableMarketTypes) -> Dict:
        """Select market dict based on the market class type."""
        if market_type == AvailableMarketTypes.SPOT:
            return self.markets
        if market_type == AvailableMarketTypes.SETTLEMENT:
            return self.settlement_markets
        if market_type == AvailableMarketTypes.BALANCING:
            return self.balancing_markets
        if market_type in FORWARD_MARKET_TYPES:
            return self.forward_markets

        assert False, f"Market type not supported {market_type}"

    def create_new_spot_market(
        self, current_time: DateTime, market_type: AvailableMarketTypes, area: "Area"
    ) -> bool:
        """Create spot markets according to the market count."""
        markets = self.get_market_instances_from_class_type(market_type)
        market_class = self._select_market_class(market_type)

        changed = False
        if not markets or current_time not in markets:
            markets[current_time] = self._create_market(
                market_class, current_time, area, market_type
            )
            changed = True
            self.log.trace("Adding %s market", current_time.format(TIME_FORMAT))
        self._update_indexed_future_markets()
        return changed

    def create_settlement_market(self, time_slot: DateTime, area: "Area") -> None:
        """Create a new settlement market."""
        self.settlement_markets[time_slot] = self._create_market(
            market_class=SettlementMarket,
            time_slot=time_slot,
            area=area,
            market_type=AvailableMarketTypes.SETTLEMENT,
        )
        self.log.trace("Adding %s market", time_slot.format(TIME_FORMAT))

    @staticmethod
    def _create_market(
        market_class: MarketBase,
        time_slot: Optional[DateTime],
        area: "Area",
        market_type: AvailableMarketTypes,
    ) -> MarketBase:
        """Create market for specific time_slot and market type."""
        market = market_class(
            time_slot=time_slot,
            bc=area.bc,
            notification_listener=area.dispatcher.broadcast_notification,
            grid_fee_type=area.config.grid_fee_type,
            grid_fees=GridFee(
                grid_fee_percentage=area.grid_fee_percentage, grid_fee_const=area.grid_fee_constant
            ),
            name=area.name,
            in_sim_duration=is_time_slot_in_simulation_duration(time_slot, area.config),
        )
        market.set_open_market_slot_parameters(time_slot, [time_slot])

        area.dispatcher.create_market_agents(market_type, market)
        return market
