from dataclasses import dataclass
from typing import List

from gsy_framework.constants_limits import GlobalConfig
from pendulum import duration, DateTime, Duration

from gsy_e.models.market import MarketSlotParams


@dataclass
class OrderUpdaterParameters:
    """
    Parameters of the order updater class. Includes start / end energy rate and time interval
    between each price update.
    """
    update_interval: duration
    initial_rate: float
    final_rate: float

    def serialize(self):
        """Serialize parameters."""
        return {
            "update_interval": self.update_interval,
            "initial_rate": self.initial_rate,
            "final_rate": self.final_rate
        }


class OrderUpdater:
    """
    Calculate whether the price of the template strategy orders needs to be updated.
    Uses linear increase / decrease in price along the duration of a market slot.
    """
    def __init__(self, parameters: OrderUpdaterParameters,
                 market_params: MarketSlotParams):
        self._parameters = parameters
        self._market_params = market_params
        self._update_times: List[DateTime] = self._calculate_update_timepoints(
            self._market_params.opening_time,
            self._market_params.closing_time - GlobalConfig.tick_length,
            self._parameters.update_interval)

    @staticmethod
    def _calculate_update_timepoints(
            start_time: DateTime, end_time: DateTime, interval: Duration) -> List[DateTime]:
        current_time = start_time
        timepoints = []
        while current_time < end_time:
            timepoints.append(current_time)
            current_time += interval
        timepoints.append(end_time)
        return timepoints

    def is_time_for_update(
            self, current_time_slot: DateTime) -> bool:
        """Check if the orders need to be updated."""
        return current_time_slot in self._update_times

    def get_energy_rate(self, current_time_slot: DateTime) -> float:
        """Calculate energy rate for the current time slot."""
        assert current_time_slot >= self._market_params.opening_time
        if current_time_slot == self._market_params.closing_time - GlobalConfig.tick_length:
            return self._parameters.final_rate
        time_elapsed_since_start = current_time_slot - self._market_params.opening_time
        total_slot_length = (
                self._market_params.closing_time - self._market_params.opening_time)
        rate_range = abs(self._parameters.final_rate - self._parameters.initial_rate)
        rate_diff_from_initial = (time_elapsed_since_start / total_slot_length) * rate_range
        if self._parameters.initial_rate < self._parameters.final_rate:
            return self._parameters.initial_rate + rate_diff_from_initial

        assert (self._parameters.initial_rate - rate_diff_from_initial) >= 0.
        return self._parameters.initial_rate - rate_diff_from_initial
