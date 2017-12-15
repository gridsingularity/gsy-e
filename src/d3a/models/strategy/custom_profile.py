import csv
from collections import defaultdict
from itertools import dropwhile
import json
from typing import Dict  # noqa

from pendulum import Interval, parse, Pendulum
from pendulum import Time  # noqa

from d3a.models.strategy.base import BaseStrategy


class CustomProfile:
    """Compute energy needed/produced by owning strategy"""

    def __init__(self, strategy, *,
                 values=None, start_time=Pendulum.now(), time_step=Interval(seconds=1)):
        assert isinstance(strategy, CustomProfileStrategy), \
               "CustomProfile should only be used with CustomProfileStrategy"
        self.strategy = strategy
        self.set_from_list(values or [], start_time, time_step)

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


class CustomProfileIrregularTimes:
    def __init__(self, strategy):
        assert isinstance(strategy, CustomProfileStrategy), \
            "CustomProfile should only be used with CustomProfileStrategy"
        self.strategy = strategy
        self.time_step = Interval(minutes=1)

    def _time_offset(self, time):
        return int((time - self.start_time).as_interval() / self.time_step)

    def set_from_dict(self, data):
        self.start_time = min(data.keys())
        self.times = tuple(self._time_offset(key) for key in sorted(data.keys()))
        self.values = tuple(item[1] for item in sorted(data.items(), key=lambda item: item[0]))

    def power_at(self, time):
        offset = self._time_offset(time)
        if not self.times[0] <= offset < self.times[-1]:
            return 0.0
        for i in range(len(self.times)-1):
            if offset < self.times[i+1]:
                return self.values[i]
        else:
            assert False, "Loop should find a time."

    def amount_over_period(self, period_start, duration):
        start_offset = self._time_offset(period_start)
        if not 0 <= start_offset < self.times[-1]:
            return 0.0
        end = start_offset + int(duration / self.time_step)
        times = dropwhile(lambda j: self.times[j] <= start_offset, range(1, len(self.times)))
        i = next(times)
        amount = self.values[i-1] * (self.times[i] - start_offset)
        for i in times:
            if self.times[i] >= end:
                amount += self.values[i-1] * (end - self.times[i-1])
                break
            else:
                amount += self.values[i-1] * (self.times[i] - self.times[i-1])
        return amount


class CustomProfileStrategy(BaseStrategy):
    """Strategy for a given load and production profile"""

    def __init__(self, *, profile_type=CustomProfile):
        super().__init__()
        self.profile = profile_type(self)
        self.slot_load = {}  # type: Dict[Time, float]
        self.bought = defaultdict(float)

    def _update_slots(self):
        self.slot_load = {
            slot_time: self.profile.amount_over_period(slot_time, self.owner.config.slot_length)
            for slot_time in self.owner.markets
        }

    def event_activate(self):
        self._update_slots()

    def event_market_cycle(self):
        self._update_slots()

    def event_tick(self, *, area):
        if area == self.owner:
            for slot, market in area.markets.items():
                for offer in market.sorted_offers:
                    missing = self.slot_load[slot] - self.bought[slot]
                    if missing == 0:
                        break
                    energy = min(offer.energy, missing)
                    self.accept_offer(market, offer, energy=energy)
                    self.bought[slot] += energy


def custom_profile_strategy_from_json(json_str):
    strategy = CustomProfileStrategy(profile_type=CustomProfileIrregularTimes)
    strategy.profile.set_from_dict(json.loads(json_str))
    return strategy


def custom_profile_strategy_from_csv(csv_data):
    data = {}
    for row in csv.reader(csv_data):
        try:
            data[parse(row[0])] = float(row[1])
        except ValueError:
            pass  # TODO
            # area.log.error("Could not parse csv file, skipping line: {}".format(row))
    strategy = CustomProfileStrategy(profile_type=CustomProfileIrregularTimes)
    strategy.profile.set_from_dict(data)
    return strategy


def custom_profile_strategy_from_csv_file(filename):
    try:
        with open(filename, 'r') as data:
            return custom_profile_strategy_from_csv(data)
    except FileNotFoundError:
        return None
