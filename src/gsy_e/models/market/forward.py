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

from dataclasses import dataclass
from abc import abstractmethod
from typing import Optional, TYPE_CHECKING, List, Dict

from gsy_framework.constants_limits import ConstSettings
from pendulum import DateTime, duration

from gsy_e.gsy_e_core.blockchain_interface import NonBlockchainInterface
from gsy_e.models.market import GridFee
from gsy_e.models.market.future import FutureMarkets

if TYPE_CHECKING:
    from gsy_e.models.config import SimulationConfig
    from gsy_e.models.area.event_dispatcher import AreaDispatcher


@dataclass(frozen=True)
class ForwardMarketSlot:
    """Parameters that describe a forward market slot."""
    opening_time: DateTime
    closing_time: DateTime
    delivery_start_time: DateTime
    delivery_end_time: DateTime


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
        self._open_market_slots: Dict[DateTime, ForwardMarketSlot] = {}

    @staticmethod
    @abstractmethod
    def _get_start_time(current_time: DateTime) -> DateTime:
        """Return time when the market block starts."""

    @staticmethod
    @abstractmethod
    def _get_end_time(current_time: DateTime) -> DateTime:
        """Return time when the market block ends."""

    @abstractmethod
    def _calculate_closing_time(self, delivery_time: DateTime) -> DateTime:
        """
        Retrieves the time duration from the time that the market closes till the time that the
        traded energy should be delivered.
        """

    @staticmethod
    @abstractmethod
    def _get_market_slot_duration(current_time: DateTime, _config) -> duration:
        """Return duration of market slots inside the market block."""

    def create_future_market_slots(self, current_market_time_slot: DateTime,
                                   config: "SimulationConfig") -> List[DateTime]:
        if not ConstSettings.ForwardMarketSettings.ENABLE_FORWARD_MARKETS:
            return []
        created_future_slots = self._create_future_market_slots(
            self._get_start_time(current_market_time_slot),
            self._get_end_time(current_market_time_slot), config)

        self._set_open_market_slot_parameters(current_market_time_slot, created_future_slots)

        return created_future_slots

    @property
    def open_market_slot_info(self) -> Dict[DateTime, ForwardMarketSlot]:
        """Retrieve the parameters for the selected market slot."""
        return self._open_market_slots

    def _set_open_market_slot_parameters(
            self, current_market_slot: DateTime, created_market_slots: List[DateTime]):
        """Update the parameters of the newly opened market slots."""
        for market_slot in created_market_slots:
            if market_slot in self._open_market_slots:
                continue

            self._open_market_slots[market_slot] = ForwardMarketSlot(
                delivery_start_time=market_slot,
                delivery_end_time=(
                        market_slot + self._get_market_slot_duration(market_slot, None)),
                opening_time=current_market_slot,
                closing_time=self._calculate_closing_time(market_slot)
            )


class IntradayMarket(ForwardMarketBase):
    """Intraday market block implementation"""

    @staticmethod
    def _get_start_time(current_time: DateTime) -> DateTime:
        return current_time.add(minutes=30)

    @staticmethod
    def _get_end_time(current_time: DateTime) -> DateTime:
        return current_time.add(days=1)

    @staticmethod
    def _get_market_slot_duration(_current_time: DateTime, _config) -> duration:
        return duration(minutes=15)

    def _calculate_closing_time(self, delivery_time: DateTime) -> DateTime:
        """Closing time of the intraday market is 15 mins before delivery."""
        return delivery_time - duration(minutes=15)

    @property
    def type_name(self):
        return "Intraday Forward Market"


class DayForwardMarket(ForwardMarketBase):
    """Day forward market implementation"""

    @staticmethod
    def _get_start_time(current_time: DateTime) -> DateTime:
        return current_time.add(hours=2)

    @staticmethod
    def _get_end_time(current_time: DateTime) -> DateTime:
        return current_time.add(weeks=1)

    @staticmethod
    def _get_market_slot_duration(_current_time: DateTime, _config) -> duration:
        return duration(hours=1)

    def _calculate_closing_time(self, delivery_time: DateTime) -> DateTime:
        """
        Closing time of the day ahead market is one hour before delivery.
        """
        return delivery_time.set(minute=0).subtract(hours=1)

    @property
    def type_name(self):
        return "Day Forward Market"


class WeekForwardMarket(ForwardMarketBase):
    """Week forward market implementation"""

    @staticmethod
    def _get_start_time(current_time: DateTime) -> DateTime:
        days_until_next_monday = 7 - (current_time.day_of_week - 1)
        return current_time.set(hour=0, minute=0).add(days=days_until_next_monday).add(weeks=1)

    @staticmethod
    def _get_end_time(current_time: DateTime) -> DateTime:
        return current_time.set(hour=0, minute=0).add(years=1)

    @staticmethod
    def _get_market_slot_duration(_current_time: DateTime, _config) -> duration:
        return duration(weeks=1)

    def _calculate_closing_time(self, delivery_time: DateTime) -> DateTime:
        """
        Closing time of the week market is one week before the date that the energy will be
        delivered.
        """
        return delivery_time.set(hour=0, minute=0).subtract(weeks=1)

    @property
    def type_name(self):
        return "Week Forward Market"


class MonthForwardMarket(ForwardMarketBase):
    """Month forward market implementation"""

    @staticmethod
    def _get_start_time(current_time: DateTime) -> DateTime:
        return current_time.set(day=1, hour=0, minute=0).add(months=2)

    @staticmethod
    def _get_end_time(current_time: DateTime) -> DateTime:
        return current_time.set(day=1, hour=0, minute=0).add(years=2)

    @staticmethod
    def _get_market_slot_duration(current_time: DateTime, _config) -> duration:
        return duration(months=1)

    def _calculate_closing_time(self, delivery_time: DateTime) -> DateTime:
        """
        Closing time of the monthly market is one month before the date that the energy will be
        delivered.
        """
        return delivery_time.set(day=1, hour=0, minute=0).subtract(months=1)

    @property
    def type_name(self):
        return "Month Forward Market"


class YearForwardMarket(ForwardMarketBase):
    """Year forward market implementation"""

    @staticmethod
    def _get_start_time(current_time: DateTime) -> DateTime:
        return current_time.set(month=1, day=1, hour=0, minute=0).add(years=2)

    @staticmethod
    def _get_end_time(current_time: DateTime) -> DateTime:
        return current_time.set(month=1, day=1, hour=0, minute=0).add(years=6)

    @staticmethod
    def _get_market_slot_duration(current_time: DateTime, _config) -> duration:
        return duration(years=1)

    def _calculate_closing_time(self, delivery_time: DateTime) -> DateTime:
        """
        Closing time of the yearly market is one year before the date that the energy will be
        delivered.
        """
        return delivery_time.set(month=1, day=1, hour=0, minute=0).subtract(years=1)

    @property
    def type_name(self):
        return "Year Forward Market"
