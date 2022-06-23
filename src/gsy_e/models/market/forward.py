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

from typing import Optional, TYPE_CHECKING

from gsy_framework.constants_limits import ConstSettings
from pendulum import DateTime, duration

from gsy_e.gsy_e_core.blockchain_interface import NonBlockchainInterface
from gsy_e.models.market import GridFee
from gsy_e.models.market.future import FutureMarkets

if TYPE_CHECKING:
    from gsy_e.models.config import SimulationConfig
    from gsy_e.models.area.event_dispatcher import AreaDispatcher


class ForwardMarketBase(FutureMarkets):
    """Base class for forward markets"""

    def __init__(self, bc: Optional[NonBlockchainInterface] = None,
                 notification_listener: Optional["AreaDispatcher"] = None,
                 readonly: bool = False,
                 grid_fee_type: int = ConstSettings.MASettings.GRID_FEE_TYPE,
                 grid_fees: Optional[GridFee] = None,
                 name: Optional[str] = None) -> None:
        # pylint: disable=too-many-arguments
        if not ConstSettings.ForwardMarketSettings.ENABLE_FORWARD_MARKETS:
            return

        super().__init__(bc=bc, notification_listener=notification_listener,
                         readonly=readonly, grid_fee_type=grid_fee_type,
                         grid_fees=grid_fees, name=name)

    @staticmethod
    def _get_start_time(current_time: DateTime) -> DateTime:
        """Return time when the market block starts."""

    @staticmethod
    def _get_end_time(current_time: DateTime) -> DateTime:
        """Return time when the market block ends."""

    @staticmethod
    def _get_market_slot_duration() -> duration:
        """Return duration of market slots inside the market block."""

    def create_future_markets(self, current_market_time_slot: DateTime,
                              config: "SimulationConfig") -> None:
        if not ConstSettings.ForwardMarketSettings.ENABLE_FORWARD_MARKETS:
            return
        self._create_future_markets(self._get_market_slot_duration(),
                                    self._get_start_time(current_market_time_slot),
                                    self._get_end_time(current_market_time_slot), config)


class IntradayMarket(ForwardMarketBase):
    """Intraday market block implementation"""

    @staticmethod
    def _get_start_time(current_time: DateTime) -> DateTime:
        return current_time.add(minutes=15)

    @staticmethod
    def _get_end_time(current_time: DateTime) -> DateTime:
        return current_time.add(days=1)

    @staticmethod
    def _get_market_slot_duration() -> duration:
        return duration(minutes=15)


class HourForwardMarket(ForwardMarketBase):
    """Hour forward market implementation"""

    @staticmethod
    def _get_start_time(current_time: DateTime) -> DateTime:
        return current_time.set(hour=0, minute=0).add(hours=1)

    @staticmethod
    def _get_end_time(current_time: DateTime) -> DateTime:
        return current_time.set(hour=0, minute=0).add(weeks=1)

    @staticmethod
    def _get_market_slot_duration() -> duration:
        return duration(hours=1)


class WeekForwardMarket(ForwardMarketBase):
    """Week forward market implementation"""

    @staticmethod
    def _get_start_time(current_time: DateTime) -> DateTime:
        return current_time.set(hour=0, minute=0).add(weeks=1)

    @staticmethod
    def _get_end_time(current_time: DateTime) -> DateTime:
        return current_time.set(hour=0, minute=0).add(years=1)

    @staticmethod
    def _get_market_slot_duration() -> duration:
        return duration(weeks=1)


class MonthForwardMarket(ForwardMarketBase):
    """Month forward market implementation"""

    @staticmethod
    def _get_start_time(current_time: DateTime) -> DateTime:
        return current_time.set(hour=0, minute=0).add(months=1)

    @staticmethod
    def _get_end_time(current_time: DateTime) -> DateTime:
        return current_time.set(hour=0, minute=0).add(years=2)

    @staticmethod
    def _get_market_slot_duration() -> duration:
        return duration(months=1)


class YearForwardMarket(ForwardMarketBase):
    """Year forward market implementation"""

    @staticmethod
    def _adapt_market_length(market_length: duration, time_slot: DateTime) -> duration:
        return market_length + duration(days=1) if time_slot.is_leap_year() else market_length

    @staticmethod
    def _get_start_time(current_time: DateTime) -> DateTime:
        return current_time.set(month=1, day=1, hour=0, minute=0).add(years=2)

    @staticmethod
    def _get_end_time(current_time: DateTime) -> DateTime:
        return current_time.set(month=1, day=1, hour=0, minute=0).add(years=6)

    @staticmethod
    def _get_market_slot_duration() -> duration:
        return duration(years=1)
