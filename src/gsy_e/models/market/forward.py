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

from abc import abstractmethod
from typing import Optional, TYPE_CHECKING, List

from gsy_framework.constants_limits import ConstSettings
from gsy_framework.enums import AvailableMarketTypes
from pendulum import DateTime, duration

from gsy_e.constants import FORWARD_MARKET_MAX_DURATION_YEARS
from gsy_e.gsy_e_core.blockchain_interface import NonBlockchainInterface
from gsy_e.models.market import GridFee, MarketSlotParams
from gsy_e.models.market.future import FutureMarkets

if TYPE_CHECKING:
    from gsy_e.models.config import SimulationConfig
    from gsy_e.models.area.event_dispatcher import AreaDispatcher


class ForwardMarketBase(FutureMarkets):
    """Base class for forward markets"""

    def __init__(
        self,
        bc: Optional[NonBlockchainInterface] = None,
        notification_listener: Optional["AreaDispatcher"] = None,
        readonly: bool = False,
        grid_fee_type: int = ConstSettings.MASettings.GRID_FEE_TYPE,
        grid_fees: Optional[GridFee] = None,
        name: Optional[str] = None,
    ) -> None:
        # pylint: disable=too-many-arguments
        if not ConstSettings.ForwardMarketSettings.ENABLE_FORWARD_MARKETS:
            return

        super().__init__(
            bc=bc,
            notification_listener=notification_listener,
            readonly=readonly,
            grid_fee_type=grid_fee_type,
            grid_fees=grid_fees,
            name=name,
        )

    @property
    @abstractmethod
    def market_type(self):
        """Return the market type from the AvailableMarketTypes enum."""

    def create_future_market_slots(
        self, current_market_time_slot: DateTime, config: "SimulationConfig"
    ) -> List[DateTime]:
        if not ConstSettings.ForwardMarketSettings.ENABLE_FORWARD_MARKETS:
            return []
        created_future_slots = self._create_future_market_slots(config, current_market_time_slot)

        self.set_open_market_slot_parameters(current_market_time_slot, created_future_slots)
        return created_future_slots

    def set_open_market_slot_parameters(
        self, current_market_slot: DateTime, created_market_slots: List[DateTime]
    ):
        """Update the parameters of the newly opened market slots."""
        for market_slot in created_market_slots:
            if market_slot in self._open_market_slot_parameters:
                continue

            self._open_market_slot_parameters[market_slot] = MarketSlotParams(
                delivery_start_time=market_slot,
                delivery_end_time=(market_slot + self._get_market_slot_duration(None)),
                opening_time=current_market_slot,
                closing_time=self._calculate_closing_time(market_slot),
            )


class IntradayMarket(ForwardMarketBase):
    """Intraday market block implementation"""

    @property
    def market_type(self) -> AvailableMarketTypes:
        return AvailableMarketTypes.INTRADAY

    @staticmethod
    def _get_start_time(current_time: DateTime, config: "SimulationConfig") -> DateTime:
        return current_time.add(minutes=30)

    @staticmethod
    def _get_end_time(current_time: DateTime) -> DateTime:
        return current_time.add(days=1)

    @staticmethod
    def _get_market_slot_duration(_config) -> duration:
        return duration(minutes=15)

    @staticmethod
    def _calculate_closing_time(delivery_time: DateTime) -> DateTime:
        """Closing time of the intraday market is 15 mins before delivery."""
        return delivery_time.subtract(minutes=15)

    @property
    def type_name(self):
        return "Intraday Forward Market"

    @property
    def _debug_log_market_type_identifier(self) -> str:
        return "[INTRADAY]"


class DayForwardMarket(ForwardMarketBase):
    """Day forward market implementation"""

    @property
    def market_type(self) -> AvailableMarketTypes:
        return AvailableMarketTypes.DAY_FORWARD

    @staticmethod
    def _get_start_time(current_time: DateTime, config: "SimulationConfig") -> DateTime:
        return current_time.set(hour=0, minute=0).add(days=1)

    @staticmethod
    def _get_end_time(current_time: DateTime) -> DateTime:
        return current_time.set(hour=0, minute=0).add(weeks=1, days=1, hours=-1)

    @staticmethod
    def _get_market_slot_duration(_config) -> duration:
        return duration(hours=1)

    @staticmethod
    def _calculate_closing_time(delivery_time: DateTime) -> DateTime:
        """
        Closing time of the day ahead market is one hour before delivery.
        """
        return delivery_time.subtract(days=1)

    @property
    def type_name(self):
        return "Day Forward Market"

    @property
    def _debug_log_market_type_identifier(self) -> str:
        return "[DAY]"


class WeekForwardMarket(ForwardMarketBase):
    """Week forward market implementation"""

    @property
    def market_type(self) -> AvailableMarketTypes:
        return AvailableMarketTypes.WEEK_FORWARD

    @staticmethod
    def _get_start_time(current_time: DateTime, config: "SimulationConfig") -> DateTime:
        days_until_next_monday = 7 - current_time.day_of_week
        return current_time.set(hour=0, minute=0).add(days=days_until_next_monday).add(weeks=1)

    @staticmethod
    def _get_end_time(current_time: DateTime) -> DateTime:
        return current_time.set(hour=0, minute=0).add(years=1)

    @staticmethod
    def _get_market_slot_duration(_config) -> duration:
        return duration(weeks=1)

    @staticmethod
    def _calculate_closing_time(delivery_time: DateTime) -> DateTime:
        """
        Closing time of the week market is one week before the date that the energy will be
        delivered.
        """
        return delivery_time.set(hour=0, minute=0).subtract(weeks=1)

    @property
    def type_name(self):
        return "Week Forward Market"

    @property
    def _debug_log_market_type_identifier(self) -> str:
        return "[WEEK]"


class MonthForwardMarket(ForwardMarketBase):
    """Month forward market implementation"""

    @property
    def market_type(self) -> AvailableMarketTypes:
        return AvailableMarketTypes.MONTH_FORWARD

    @staticmethod
    def _get_start_time(current_time: DateTime, config: "SimulationConfig") -> DateTime:
        return current_time.set(day=1, hour=0, minute=0).add(months=2)

    @staticmethod
    def _get_end_time(current_time: DateTime) -> DateTime:
        return current_time.set(day=1, hour=0, minute=0).add(years=2)

    @staticmethod
    def _get_market_slot_duration(_config) -> duration:
        return duration(months=1)

    @staticmethod
    def _calculate_closing_time(delivery_time: DateTime) -> DateTime:
        """
        Closing time of the monthly market is one month before the date that the energy will be
        delivered.
        """
        return delivery_time.set(day=1, hour=0, minute=0).subtract(months=1)

    @property
    def type_name(self):
        return "Month Forward Market"

    @property
    def _debug_log_market_type_identifier(self) -> str:
        return "[MONTH]"


class YearForwardMarket(ForwardMarketBase):
    """Year forward market implementation"""

    @property
    def market_type(self) -> AvailableMarketTypes:
        return AvailableMarketTypes.YEAR_FORWARD

    @staticmethod
    def _get_start_time(current_time: DateTime, config: "SimulationConfig") -> DateTime:
        return current_time.start_of("year").add(years=2)

    @staticmethod
    def _get_end_time(current_time: DateTime) -> DateTime:
        return current_time.start_of("year").add(years=FORWARD_MARKET_MAX_DURATION_YEARS)

    @staticmethod
    def _get_market_slot_duration(_config) -> duration:
        return duration(years=1)

    @staticmethod
    def _calculate_closing_time(delivery_time: DateTime) -> DateTime:
        """
        Closing time of the yearly market is one year before the date that the energy will be
        delivered.
        """
        return delivery_time.set(month=1, day=1, hour=0, minute=0).subtract(years=1)

    @property
    def type_name(self):
        return "Year Forward Market"

    @property
    def _debug_log_market_type_identifier(self) -> str:
        return "[YEAR]"
