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
from gsy_framework.constants_limits import ConstSettings
from pendulum import DateTime


class MarketCounter:
    """Base class for market counters"""

    def __init__(self, clearing_interval_min: int):
        self._last_clearing_time = None
        self.clearing_interval = clearing_interval_min

    def is_time_for_clearing(self, current_time: DateTime) -> bool:
        """Return if it is time for clearing according to self.clearing_interval."""
        if not self._last_clearing_time:
            self._last_clearing_time = current_time
            return True
        duration_in_min = (current_time - self._last_clearing_time).minutes
        if duration_in_min >= self.clearing_interval:
            self._last_clearing_time = current_time
            return True
        return False


class FutureMarketCounter(MarketCounter):
    """Hold a time counter for the future market.

    In the future market, we only want to clear in a predefined interval.
    """
    def __init__(self):
        super().__init__(
            clearing_interval_min=ConstSettings.FutureMarketSettings.
            FUTURE_MARKET_CLEARING_INTERVAL_MINUTES)

    def is_time_for_clearing(self, current_time: DateTime) -> bool:
        """Only return if future markets are enabled."""
        if ConstSettings.FutureMarketSettings.FUTURE_MARKET_DURATION_HOURS > 0:
            return super().is_time_for_clearing(current_time)
        return False


class ExternalTickCounter:
    """External tick counter."""

    def __init__(self, ticks_per_slot: int, dispatch_frequency_percent: int):
        self._dispatch_tick_frequency = int(
            ticks_per_slot *
            (dispatch_frequency_percent / 100)
        )

    def is_it_time_for_external_tick(self, current_tick_in_slot: int) -> bool:
        """Boolean return if time for external tick."""
        return current_tick_in_slot % self._dispatch_tick_frequency == 0


class ForwardMarketCounter:
    """Base class for forward market counters."""

    @staticmethod
    def is_time_for_clearing(current_time: DateTime) -> bool:
        """Return True if it is time for market clearing"""


class IntraDayMarketCounter(ForwardMarketCounter):
    """Market counter for intra-day markets."""

    @staticmethod
    def is_time_for_clearing(current_time: DateTime) -> bool:
        """Always return True because intra-day markets clear continuously."""
        return True


class DayForwardMarketCounter(ForwardMarketCounter):
    """Market counter for day-forward markets."""

    @staticmethod
    def is_time_for_clearing(current_time: DateTime) -> bool:
        return current_time.minute == 0 and current_time.second == 0


class WeekForwardMarketCounter(ForwardMarketCounter):
    """Market counter for week-forward markets."""

    @staticmethod
    def is_time_for_clearing(current_time: DateTime) -> bool:
        return (current_time.day_of_week == 1 and
                current_time.hour == 0 and
                current_time.minute == 0 and
                current_time.second == 0)


class MonthForwardMarketCounter(ForwardMarketCounter):
    """Market counter for month-forward markets."""

    @staticmethod
    def is_time_for_clearing(current_time: DateTime) -> bool:
        return (current_time.day == 1 and
                current_time.hour == 0 and
                current_time.minute == 0 and
                current_time.second == 0)


class YearForwardMarketCounter(ForwardMarketCounter):
    """Market counter for year-forward markets."""

    @staticmethod
    def is_time_for_clearing(current_time: DateTime) -> bool:
        return (current_time.month in [1, 7] and
                current_time.day == 1 and
                current_time.hour == 0 and
                current_time.minute == 0 and
                current_time.second == 0)


class IntradayMarketCounter(ForwardMarketCounter):
    """Handle timing of intraday market clearing"""

    @staticmethod
    def is_time_for_clearing(current_time: DateTime) -> bool:
        return (current_time.minute % 15 == 0 and
                current_time.second == 0)
