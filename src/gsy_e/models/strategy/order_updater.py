from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, Union, List

from gsy_framework.constants_limits import ConstSettings
from gsy_framework.exceptions import GSyException
from gsy_framework.utils import convert_pendulum_to_str_in_dict
from pendulum import duration, DateTime, Duration

from gsy_e.models.market import MarketSlotParams


@dataclass
class OrderUpdaterParameters:
    """
    Parameters of the order updater class. Includes start / end energy rate and time interval
    between each price update.
    """

    update_interval: Optional[duration]
    initial_rate: Optional[Union[dict[DateTime, float], float]]
    final_rate: Optional[Union[dict[DateTime, float], float]]

    def serialize(self):
        """Serialize parameters."""
        return {
            "update_interval": self.get_update_interval(),
            "initial_rate": (
                self.initial_rate
                if isinstance(self.initial_rate, (type(None), float, int))
                else convert_pendulum_to_str_in_dict(self.initial_rate)
            ),
            "final_rate": (
                self.final_rate
                if isinstance(self.final_rate, (type(None), float, int))
                else convert_pendulum_to_str_in_dict(self.final_rate)
            ),
        }

    def get_update_interval(self):
        """Return update_interval. If not set, return default value."""
        if self.update_interval is None:
            return duration(minutes=ConstSettings.GeneralSettings.DEFAULT_UPDATE_INTERVAL)
        return self.update_interval

    @staticmethod
    def _get_default_value_initial_rate(_time_slot: DateTime):
        return 0

    @staticmethod
    def _get_default_value_final_rate(_time_slot: DateTime):
        return 0

    def get_initial_rate(self, time_slot: DateTime) -> float:
        """Return initial rate for time slot. If not set, return default value."""
        if self.initial_rate is None:
            return self._get_default_value_initial_rate(time_slot)
        if isinstance(self.initial_rate, (float, int)):
            return self.initial_rate
        try:
            return self.initial_rate[time_slot]
        except KeyError as exc:
            raise GSyException(
                f"Initial rate profile does not contain timestamp {time_slot}"
            ) from exc

    def get_final_rate(self, time_slot: DateTime) -> float:
        """Return final rate for time slot. If not set, return default value."""
        if self.final_rate is None:
            return self._get_default_value_final_rate(time_slot)
        if isinstance(self.final_rate, (float, int)):
            return self.final_rate
        try:
            return self.final_rate[time_slot]
        except KeyError as exc:
            raise GSyException(
                f"Final rate profile does not contain timestamp {time_slot}"
            ) from exc


class OrderUpdater:
    """
    Calculate whether the price of the template strategy orders needs to be updated.
    Uses linear increase / decrease in price along the duration of a market slot.
    """

    def __init__(self, parameters: OrderUpdaterParameters, market_params: MarketSlotParams):

        self._initial_rate = Decimal(parameters.get_initial_rate(market_params.opening_time))
        self._final_rate = Decimal(parameters.get_final_rate(market_params.opening_time))
        # in order to make sure that the final rate is indeed reached, we add a tolerance
        self._update_interval = parameters.get_update_interval()
        self._market_params = market_params
        self._update_times: List[DateTime] = self._calculate_update_timepoints(
            self._market_params.opening_time,
            self._market_params.closing_time - self._update_interval,
            self._update_interval,
        )

    @staticmethod
    def _calculate_update_timepoints(
        start_time: DateTime, end_time: DateTime, interval: Duration
    ) -> List[DateTime]:
        current_time = start_time
        timepoints = []
        while current_time < end_time:
            timepoints.append(current_time)
            current_time += interval
        timepoints.append(end_time)
        return timepoints

    def is_time_for_update(self, current_time: DateTime) -> bool:
        """Check if the orders need to be updated."""
        return current_time in self._update_times

    def get_energy_rate(self, current_time: DateTime) -> Decimal:
        """Calculate energy rate for the current time slot."""
        assert current_time >= self._market_params.opening_time
        time_elapsed_since_start = current_time - self._market_params.opening_time
        total_slot_length = (
            self._market_params.closing_time
            - self._update_interval
            - self._market_params.opening_time
        )
        rate_range = abs(self._final_rate - self._initial_rate)
        rate_diff_from_initial = Decimal(time_elapsed_since_start / total_slot_length) * rate_range

        if self._initial_rate < self._final_rate:
            return self._initial_rate + rate_diff_from_initial

        assert (self._initial_rate - rate_diff_from_initial) >= 0.0
        return self._initial_rate - rate_diff_from_initial
