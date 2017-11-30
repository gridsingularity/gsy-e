from collections import defaultdict
from typing import Dict  # noqa

from pendulum import Interval, Pendulum
from pendulum import Time  # noqa

from d3a.models.strategy.base import BaseStrategy


class CustomProfile:
    """Compute energy needed/produced by owning strategy"""

    def __init__(self, strategy, *,
                 values=[], start_time=Pendulum.now(), time_step=Interval(seconds=1)):
        assert isinstance(strategy, CustomProfileStrategy), \
               "CustomProfile should only be used with CustomProfileStrategy"
        self.strategy = strategy
        self.set_from_list(values, start_time, time_step)

    def set_from_list(self, values, start_time, time_step):
        self.values = tuple(values)
        self.start_time = start_time
        self.time_step = time_step
        self.factor = time_step / Interval(hours=1)

    def _value(self, index):
        if not 0 <= index < len(self.values):
            self.strategy.log.warning(
                "CustomProfile: no value for queried time set, using 0 as default value"
            )
            return 0.0
        return self.values[index]

    def power_at(self, time):
        return self._value(int((time - self.start_time).as_interval() / self.time_step))

    def amount_over_period(self, period_start, duration):
        start = int((period_start - self.start_time).as_interval() / self.time_step)
        end = start + int(duration / self.time_step)
        return self.factor * sum(self._value(index) for index in range(start, end))


class CustomProfileStrategy(BaseStrategy):
    """Strategy for a given load and production profile"""

    def __init__(self, area, *, profile_type=CustomProfile):
        super().__init__()
        self.area = area
        self.profile = profile_type(self)
        self.slot_load = {}  # type: Dict[Time, float]
        self.bought = defaultdict(float)

    def _update_slots(self):
        self.slot_load = {
            slot_time: self.profile.amount_over_period(slot_time, self.area.config.slot_length)
            for slot_time in self.area.markets
        }

    def event_activate(self):
        self._update_slots()

    def event_market_cycle(self):
        self._update_slots()

    def event_tick(self, *, area):
        for slot, market in self.area.markets.items():
            for offer in market.sorted_offers:
                if self.bought[slot] < self.slot_load[slot]:
                    self.accept_offer(market, offer)
                    self.bought[slot] += offer.energy
