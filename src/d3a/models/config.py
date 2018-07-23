import ast
from pendulum.interval import Interval

from d3a.exceptions import D3AException
from d3a.util import format_interval
from d3a.models.strategy.const import ConstSettings

from logging import getLogger
log = getLogger(__name__)


class SimulationConfig:
    def __init__(self, duration: Interval, slot_length: Interval, tick_length: Interval,
                 market_count: int, cloud_coverage: int, market_maker_rate, iaa_fee: int):
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
        # TODO: Once the d3a uses a common API to the d3a-web, this should be removed
        # since this limitation already exists on d3a-web
        if 0 <= cloud_coverage <= 2:
            self.cloud_coverage = cloud_coverage
        else:
            raise D3AException("Invalid cloud coverage value ({}).".format(cloud_coverage))

        self.market_maker_rate = {}
        self.read_market_maker_rate(market_maker_rate)
        if iaa_fee is None:
            self.iaa_fee = ConstSettings.INTER_AREA_AGENT_FEE_PERCENTAGE
        else:
            self.iaa_fee = iaa_fee

    def __repr__(self):
        return (
            "<SimulationConfig("
            "duration='{s.duration}', "
            "slot_length='{s.slot_length}', "
            "tick_length='{s.tick_length}', "
            "market_count='{s.market_count}', "
            "ticks_per_slot='{s.ticks_per_slot}', "
            "cloud_coverage='{s.cloud_coverage}', "
            "market_maker_rate='{s.market_maker_rate}', "
            ")>"
        ).format(s=self)

    def as_dict(self):
        fields = {'duration', 'slot_length', 'tick_length', 'market_count', 'ticks_per_slot',
                  'total_ticks', 'cloud_coverage'}
        return {
            k: format_interval(v) if isinstance(v, Interval) else v
            for k, v in self.__dict__.items()
            if k in fields
        }

    def read_market_maker_rate(self, market_maker_rate):
        """
        Creates dictionary that contains the market_maker_rate for 24h
        If market_maker_rate is an int, a constant market_maker_rate is applied for each
        hourly time step.
        If market_maker_rate is a dict, the dict is interpolated for possible gaps.
        Here, for the time steps without MMR value, the previous one is used.
        :param market_maker_rate: dict
        """
        market_maker_rate_parsed = ast.literal_eval(str(market_maker_rate))
        if type(market_maker_rate_parsed) == int:
            self.market_maker_rate = {k: market_maker_rate_parsed for k in range(24)}
        elif type(market_maker_rate_parsed) == dict:
            market_maker_rate_profile = market_maker_rate_parsed

            current_mmr = market_maker_rate_parsed[next(iter(market_maker_rate_parsed))]
            for ti in range(24):
                if not (ti in market_maker_rate_parsed.keys()):
                    market_maker_rate_profile[ti] = current_mmr
                else:
                    current_mmr = market_maker_rate_parsed[ti]

            if sorted(market_maker_rate_profile.keys()) != list(range(24)):
                raise TypeError('Market maker rate profile failed to be parsed.'
                                ' Incomplete hour mapping.')
            self.market_maker_rate = market_maker_rate_profile
        else:
            raise D3AException("Invalid market_maker_rate value ({}).".
                               format(market_maker_rate_parsed))
