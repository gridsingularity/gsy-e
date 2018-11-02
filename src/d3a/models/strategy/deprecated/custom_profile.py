import csv
from collections import defaultdict
from contextlib import contextmanager
from itertools import dropwhile
import json
from math import ceil, floor
from typing import Dict  # noqa

from pendulum import duration, parse
from pendulum import Time  # noqa

from d3a.models.strategy import BaseStrategy


class CustomProfile:
    """Compute energy needed/produced by owning strategy"""

    def __init__(self, strategy, *,
                 values=None, start_time=None, time_step=duration(seconds=1)):
        assert isinstance(strategy, CustomProfileStrategy), \
               "CustomProfile should only be used with CustomProfileStrategy"
        self.strategy = strategy
        self.set_from_list(values or [], start_time, time_step)

    def set_from_list(self, values, start_time=None, time_step=duration(seconds=1)):
        self.values = tuple(values)
        self.start_time = start_time
        self.time_step = time_step
        self.factor = time_step / duration(hours=1)

    def _value(self, index):
        if not 0 <= index < len(self.values):
            if len(self.values) > 0:
                self.strategy.log.warning(
                    "CustomProfile: no value for queried time set, using 0 as default value"
                )
            return 0.0
        return self.values[index]

    def power_at(self, time):
        return self._value(int((time - self.start_time).as_interval() / self.time_step))

    def amount_over_period(self, period_start, duration):
        if len(self.values) == 0:
            return 0.0
        start = (period_start - self.start_time).as_interval() / self.time_step
        end = start + duration / self.time_step
        if end <= ceil(start):
            value = (end - start) * self._value(int(start))
        else:
            value = (ceil(start) - start) * self._value(int(start))
            value += sum(self._value(i) for i in range(int(ceil(start)), int(end)))
            value += (end - floor(end)) * self._value(int(end))
        return self.factor * value


class CustomProfileIrregularTimes:
    def __init__(self, strategy):
        assert isinstance(strategy, CustomProfileStrategy), \
            "CustomProfile should only be used with CustomProfileStrategy"
        self.strategy = strategy
        self.time_step = duration(minutes=1)

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
            assert False

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
        self.consumption = profile_type(self)
        self.production = profile_type(self)
        self.offer_price = 29.9
        self.slot_load = {}  # type: Dict[Time, float]
        self.bought = defaultdict(float)

    def _update_slots(self):
        self.slot_load = {
            time: self.consumption.amount_over_period(time, self.owner.config.slot_length)
            for time in self.owner.parent.markets
        }
        self.slot_prod = {
            time: self.production.amount_over_period(time, self.owner.config.slot_length)
            for time in self.owner.parent.markets
        }

    def event_activate(self):
        if self.consumption.start_time is None:
            self.consumption.start_time = self.owner.now
        self._update_slots()

    def event_market_cycle(self):
        self._update_slots()

    def event_tick(self, *, area):
        if area == self.owner.parent:
            for slot, market in area.markets.items():
                balance = self.slot_prod[slot] - self.slot_load[slot]
                if balance > 0:
                    market.offer(self.offer_price * balance, balance, self.owner.name)
                else:
                    for offer in market.sorted_offers:
                        missing = - balance - self.bought[slot]
                        if missing == 0:
                            break
                        energy = min(offer.energy, missing)
                        self.accept_offer(market, offer, energy=energy)
                        self.bought[slot] += energy


def custom_profile_strategy_from_json(consumption, production=None):
    strategy = CustomProfileStrategy(profile_type=CustomProfileIrregularTimes)
    if consumption is not None:
        strategy.consumption.set_from_dict(json.loads(consumption))
    if production is not None:
        strategy.production.set_from_dict(json.loads(production))
    return strategy


def _data_from_csv(csv_data, log):
    data = {}
    for row in csv.reader(csv_data):
        try:
            data[parse(row[0])] = float(row[1])
        except ValueError:
            if log:
                log.error("Could not parse csv file, skipping line: {}".format(row))
    return data


def custom_profile_strategy_from_csv(consumption, production, *, log=None):
    strategy = CustomProfileStrategy(profile_type=CustomProfileIrregularTimes)
    if consumption is not None:
        strategy.consumption.set_from_dict(_data_from_csv(consumption, log))
    if production is not None:
        strategy.production.set_from_dict(_data_from_csv(production, log))
    return strategy


@contextmanager
def file_option(name):
    if name is not None:
        file = open(name, 'r')
        yield file
        file.close()
    else:
        yield None


def custom_profile_strategy_from_csv_file(consumption, production, *, log=None):
    with file_option(consumption) as consumption_file:
        with file_option(production) as production_file:
            custom_profile_strategy_from_csv(consumption_file, production_file, log=log)


def custom_profile_strategy_from_list(*, consumption=None, production=None,
                                      time_step=duration(seconds=1), start_time=None):
    strategy = CustomProfileStrategy()
    if consumption is not None:
        strategy.consumption.set_from_list(consumption, start_time, time_step)
    if production is not None:
        strategy.production.set_from_list(production, start_time, time_step)
    return strategy
