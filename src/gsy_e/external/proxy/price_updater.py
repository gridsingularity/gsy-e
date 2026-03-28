from __future__ import annotations

from decimal import Decimal
from typing import List

from pendulum import DateTime, Duration


class SlotPriceUpdater:
    """
    Linearly interpolates a bid or offer price across a market slot.

    For **bids** pass ``initial_rate=min_price, final_rate=max_price``
    (price rises over time — the buyer is increasingly willing to pay).

    For **offers** pass ``initial_rate=max_price, final_rate=min_price``
    (price falls over time — the seller becomes more eager to sell).
    """

    # pylint: disable=too-many-arguments,too-many-positional-arguments
    def __init__(
        self,
        initial_rate: Decimal,
        final_rate: Decimal,
        opening_time: DateTime,
        closing_time: DateTime,
        update_interval: Duration,
    ) -> None:
        self._initial_rate = initial_rate
        self._final_rate = final_rate
        self._opening_time = opening_time
        self._closing_time = closing_time
        self._update_interval = update_interval
        self._update_times: List[DateTime] = self._compute_update_times()

    def _compute_update_times(self) -> List[DateTime]:
        # The last update timepoint is one interval before closing so that the
        # final rate is reached while there is still time to act on it.
        end = self._closing_time - self._update_interval
        times: List[DateTime] = []
        t = self._opening_time
        while t < end:
            times.append(t)
            t = t + self._update_interval
        times.append(end)
        return times

    def is_time_for_update(self, now: DateTime) -> bool:
        """Return ``True`` when ``now`` coincides with a scheduled price update."""
        return now in self._update_times

    def get_rate(self, now: DateTime) -> Decimal:
        """Return the linearly interpolated rate at ``now``."""
        if now <= self._opening_time:
            return self._initial_rate
        effective_end = self._closing_time - self._update_interval
        if now >= effective_end:
            return self._final_rate
        elapsed = now - self._opening_time
        total = effective_end - self._opening_time
        fraction = Decimal(str(elapsed / total))
        rate_range = abs(self._final_rate - self._initial_rate)
        delta = fraction * rate_range
        if self._initial_rate <= self._final_rate:
            return self._initial_rate + delta
        return self._initial_rate - delta
