from pendulum.interval import Interval

from d3a.exceptions import D3AException
from d3a.util import format_interval


class SimulationConfig:
    def __init__(self, duration: Interval, slot_length: Interval, tick_length: Interval,
                 market_count: int):
        self.duration = duration
        self.slot_length = slot_length
        self.tick_length = tick_length
        self.market_count = market_count
        self.ticks_per_slot = self.slot_length / self.tick_length
        if self.ticks_per_slot != int(self.ticks_per_slot):
            raise D3AException(
                "Non integer ticks per slot ({}) are not supported. "
                "Adjust simulation parameters.".format(self.ticks_per_slot))
        self.ticks_per_slot = int(self.ticks_per_slot)
        if self.ticks_per_slot < 10:
            raise D3AException("Too few ticks per slot ({}). Adjust simulation parameters".format(
                self.ticks_per_slot
            ))
        self.total_ticks = self.duration // self.slot_length * self.ticks_per_slot

    def __repr__(self):
        return (
            "<SimulationConfig("
            "duration='{s.duration}', "
            "slot_length='{s.slot_length}', "
            "tick_length='{s.tick_length}', "
            "market_count='{s.market_count}', "
            "ticks_per_slot='{s.ticks_per_slot}'"
            ")>"
        ).format(s=self)

    def as_dict(self):
        fields = {'duration', 'slot_length', 'tick_length', 'market_count', 'ticks_per_slot',
                  'total_ticks'}
        return {
            k: format_interval(v) if isinstance(v, Interval) else v
            for k, v in self.__dict__.items()
            if k in fields
        }
