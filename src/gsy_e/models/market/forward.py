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
from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING, List

from gsy_framework.constants_limits import ConstSettings
from gsy_framework.enums import AvailableMarketTypes
from pendulum import DateTime, duration

from gsy_e.gsy_e_core.blockchain_interface import NonBlockchainInterface
from gsy_e.models.market import GridFee
from gsy_e.models.market.future import FutureMarkets

if TYPE_CHECKING:
    from gsy_e.models.config import SimulationConfig
    from gsy_e.models.area.event_dispatcher import AreaDispatcher


@dataclass(frozen=True)
class ForwardMarketSlotParameters:
    """Parameters that describe a forward market slot."""
    open_timestamp: DateTime
    close_timestamp: DateTime
    delivery_start_timestamp: DateTime
    delivery_end_timestamp: DateTime

    def __post_init__(self):
        assert self.delivery_end_timestamp > self.delivery_start_timestamp
        assert self.close_timestamp < self.delivery_start_timestamp
        assert self.close_timestamp > self.open_timestamp


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
        self._open_market_slot_parameters = {}

    @property
    def uses_ssp_product(self) -> bool:
        """Should the market use the SSP product or energy values."""
        return self.market_type in [
            AvailableMarketTypes.YEAR_FORWARD,
            AvailableMarketTypes.MONTH_FORWARD,
            AvailableMarketTypes.WEEK_FORWARD
        ]

    @property
    @abstractmethod
    def market_type(self):
        """Return the market type from the AvailableMarketTypes enum."""

    @staticmethod
    @abstractmethod
    def _get_start_time(current_time: DateTime) -> DateTime:
        """Return time when the market block starts."""

    @staticmethod
    @abstractmethod
    def _get_end_time(current_time: DateTime) -> DateTime:
        """Return time when the market block ends."""

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
            self._get_end_time(current_market_time_slot), config,
            current_market_time_slot)

        self._set_open_market_slot_parameters(current_market_time_slot, created_future_slots)
        return created_future_slots

    def get_market_parameters_for_market_slot(
            self, market_slot: DateTime) -> ForwardMarketSlotParameters:
        """Retrieve the parameters for the selected market slot."""
        return self._open_market_slot_parameters.get(market_slot)

    def _set_open_market_slot_parameters(
            self, current_market_slot: DateTime, created_market_slots: List[DateTime]):
        """Update the parameters of the newly opened market slots."""
        for market_slot in created_market_slots:
            if market_slot in self._open_market_slot_parameters:
                continue

            self._open_market_slot_parameters[market_slot] = ForwardMarketSlotParameters(
                delivery_start_timestamp=market_slot,
                delivery_end_timestamp=(
                        market_slot + self._get_market_slot_duration(market_slot, None)),
                open_timestamp=current_market_slot,
                close_timestamp=market_slot - self._time_from_market_close_till_delivery
            )


class IntradayMarket(ForwardMarketBase):
    """Intraday market block implementation"""

    @property
    def market_type(self) -> AvailableMarketTypes:
        return AvailableMarketTypes.INTRADAY

    @staticmethod
    def _get_start_time(current_time: DateTime) -> DateTime:
        return current_time.add(minutes=15)

    @staticmethod
    def _get_end_time(current_time: DateTime) -> DateTime:
        return current_time.add(days=1)

    @staticmethod
    def _get_market_slot_duration(_current_time: DateTime, _config) -> duration:
        return duration(minutes=15)

    @property
    def _time_from_market_close_till_delivery(self) -> duration:
        return duration(minutes=15)

    @property
    def type_name(self):
        return "Intraday Forward Market"


class DayForwardMarket(ForwardMarketBase):
    """Day forward market implementation"""

    @property
    def market_type(self) -> AvailableMarketTypes:
        return AvailableMarketTypes.DAY_FORWARD

    @staticmethod
    def _get_start_time(current_time: DateTime) -> DateTime:
        return current_time.set(hour=0, minute=0).add(days=1)

    @staticmethod
    def _get_end_time(current_time: DateTime) -> DateTime:
        return current_time.set(hour=0, minute=0).add(weeks=1, days=1, hours=-1)

    @staticmethod
    def _get_market_slot_duration(_current_time: DateTime, _config) -> duration:
        return duration(hours=1)

    @property
    def _time_from_market_close_till_delivery(self) -> duration:
        return duration(days=1)

    @property
    def type_name(self):
        return "Day Forward Market"


class WeekForwardMarket(ForwardMarketBase):
    """Week forward market implementation"""

    @property
    def market_type(self) -> AvailableMarketTypes:
        return AvailableMarketTypes.WEEK_FORWARD

    @staticmethod
    def _get_start_time(current_time: DateTime) -> DateTime:
        days_until_next_monday = 7 - (current_time.day_of_week - 1)
        return current_time.set(hour=0, minute=0).add(days=days_until_next_monday)

    @staticmethod
    def _get_end_time(current_time: DateTime) -> DateTime:
        return current_time.set(hour=0, minute=0).add(years=1)

    @staticmethod
    def _get_market_slot_duration(_current_time: DateTime, _config) -> duration:
        return duration(weeks=1)

    @property
    def _time_from_market_close_till_delivery(self) -> duration:
        return duration(weeks=1)

    @property
    def type_name(self):
        return "Week forward Market"


class MonthForwardMarket(ForwardMarketBase):
    """Month forward market implementation"""

    @property
    def market_type(self) -> AvailableMarketTypes:
        return AvailableMarketTypes.MONTH_FORWARD

    @staticmethod
    def _get_start_time(current_time: DateTime) -> DateTime:
        return current_time.set(day=1, hour=0, minute=0).add(months=1)

    @staticmethod
    def _get_end_time(current_time: DateTime) -> DateTime:
        return current_time.set(day=1, hour=0, minute=0).add(years=2)

    @staticmethod
    def _get_market_slot_duration(current_time: DateTime, _config) -> duration:
        return duration(months=1)

    @property
    def _time_from_market_close_till_delivery(self) -> duration:
        return duration(months=1)

    @property
    def type_name(self):
        return "Month Forward Market"


class YearForwardMarket(ForwardMarketBase):
    """Year forward market implementation"""

    @property
    def market_type(self) -> AvailableMarketTypes:
        return AvailableMarketTypes.YEAR_FORWARD

    @staticmethod
    def _get_start_time(current_time: DateTime) -> DateTime:
        return current_time.set(month=1, day=1, hour=0, minute=0).add(years=2)

    @staticmethod
    def _get_end_time(current_time: DateTime) -> DateTime:
        return current_time.set(month=1, day=1, hour=0, minute=0).add(years=6)

    @staticmethod
    def _get_market_slot_duration(current_time: DateTime, _config) -> duration:
        return duration(years=1)

    @property
    def _time_from_market_close_till_delivery(self) -> duration:
        return duration(years=1)

    @property
    def type_name(self):
        return "Year Froward Market"
