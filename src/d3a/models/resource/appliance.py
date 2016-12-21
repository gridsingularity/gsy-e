from d3a.models.area import Area
from d3a.models.strategy.base import BaseStrategy
from typing import List, Union
from enum import Enum
from d3a.models.resource.properties import ApplianceProperties, ElectricalProperties, MeasurementParamType
from logging import getLogger
from d3a.util import TaggedLogWrapper
import random
from d3a.models.events import AreaEvent, MarketEvent
from d3a.models.resource.run_algo import RunSchedule
import math


log = getLogger(__name__)


class ApplianceMode(Enum):
    ON = 1
    OFF = 2
    IDLE = 3


class EnergyCurve:

    def __init__(self, mode: ApplianceMode, curve: List):
        self.dictModeCurve = dict()
        self.add_mode_curve(mode, curve)

    def get_mode_curve(self, mode: ApplianceMode):
        return self.dictModeCurve[mode]

    def add_mode_curve(self, mode: ApplianceMode, curve: List):
        self.dictModeCurve[mode] = curve


class UsageGenerator:
    def __init__(self, curve: List, minvariance: float = 0.0, maxvariance: float = 0.0):
        self.curve = curve
        self.minVariance = minvariance
        self.maxVariance = maxvariance
        self.log = TaggedLogWrapper(log, UsageGenerator.__name__)

    def iterator(self):
        while True:
            for data in self.curve:
                yield data

    def randomize_usage_pattern(self, curve: List):
        randomized = []
        for index in range(0, len(curve)):
            randomized.append(float(curve[index]) + random.uniform(self.minVariance, self.maxVariance))

        return randomized

    def change_curve(self, curve: List):
        self.curve = self.randomize_usage_pattern(curve)
        return self.iterator()

    def get_reading_at(self, index: int):
        val = None
        if index < 0 or index >= len(self.curve):
            val = self.curve[index]

        return val


class Appliance():

    def __init__(self, name: str = None, children: List["Area"] = None,
                 strategy: BaseStrategy = None):
        super().__init__(name, children, strategy)

        self.applianceProfile = None
        self.electricalProperties = None
        self.energyCurve = None
        self.mode = ApplianceMode.ON if self.active is True else ApplianceMode.OFF
        self.usageGenerator = None
        self.iterator = None
        self.measuring = MeasurementParamType.POWER
        self.historicUsageCurve = dict()

        self.tick_count = 0              # count to keep track of ticks since past

        self.log.debug("Appliance instantiated, current state {}, mode {}".format(self.active, self.mode))

    def start_appliance(self):
        self.log.info("Starting appliance {}".format(self.name))

        if self.electricalProperties is not None:
            self.usageGenerator = UsageGenerator(None,
                                                 self.electricalProperties.get_min_variance(),
                                                 self.electricalProperties.get_max_variance())
        else:
            self.log.error("Appliance electrical properties not set")
            return

        if self.energyCurve is not None:
            if self.energyCurve.get_mode_curve(ApplianceMode.ON) is not None:
                self.change_mode_of_operation(ApplianceMode.ON)
            else:
                self.mode = ApplianceMode.OFF
                self.log.error("Power ON energy curve is not defined for appliance")
        else:
            self.log.error("Energy curves not defined for operation modes")
            return

    def set_appliance_energy_curve(self, curve: EnergyCurve):
        """
        Set appliance consumption curve.
        :param curve: object containing energy usage curve
        """
        self.energyCurve = curve

    def set_appliance_properties(self, properties: ApplianceProperties):
        """
        Provide appliance profile details
        :param properties: Object containing appliance properties
        """
        self.applianceProfile = properties
        self.log.debug("Updated appliance properties")

    def set_electrical_properties(self, electrical: ElectricalProperties):
        """
        Provide electrical properties
        :param electrical:
        """
        self.electricalProperties = electrical
        self.log.debug("Updated electrical properties")

    def change_mode_of_operation(self, newmode: ApplianceMode):
        if self.usageGenerator is not None:
            if newmode is not None:
                if newmode != self.mode:
                    self.iterator = self.usageGenerator.change_curve(self.energyCurve.get_mode_curve(newmode))
                    self.mode = newmode
                    self.log.info("Appliance mode changed to: {}".format(newmode))
                else:
                    self.log.warning("NOOP, Appliance already in mode: {}".format(newmode))
            else:
                self.log.error("New mode not recognized")
        else:
            self.log.error("Usage generator uninitialized")

    def _cycle_markets(self):
        self.log.info("Handling market cycle")

    def tick(self):
        """
        Handle pendulum ticks
        """
        super().tick()
        usage = self.get_usage_reading()
        self.log.debug("Appliance {} usage: {}".format(usage[0], usage[1]))
        self.historicUsageCurve[self.get_now()] = usage

    def event_listener(self, event_type: Union[MarketEvent, AreaEvent], **kwargs):
        if event_type is AreaEvent.TICK:
            self.tick()
        elif event_type is AreaEvent.MARKET_CYCLE:
            self._cycle_markets()
        elif event_type is AreaEvent.ACTIVATE:
            self.activate()
        if self.strategy:
            self.strategy.event_listener(event_type, **kwargs)

    def get_historic_usage_curve(self):
        return self.historicUsageCurve

    def get_measurement_param(self) -> MeasurementParamType:
        return self.measuring

    def get_usage_reading(self) -> tuple:
        return self.measuring, self.iterator.__next__()


class PVAppliance(Appliance):

    def __init__(self, name: str = "PV", children: List["Area"] = None,
                 strategy: BaseStrategy = None):
        super().__init__(name, children, strategy)
        self.cloud_duration = 0
        self.multiplier = 1.0

    def handle_cloud_cover(self, percent: float = 0, duration: int = 0):
        """
        Method to introduce cloud cover over PV. PV will produce 0 W during cloud cover.
        :param percent: Cloud cover between 0 - 100%.
        :param duration: duration of cloud cover in ticks.
        """
        self.cloud_duration = duration
        # 2% residual power gene even under 100% cloud cover
        self.multiplier = (1 - percent / 100) if percent < 98 else 0.02
        if self.cloud_duration > 0:
            self.change_mode_of_operation(ApplianceMode.OFF)
        else:
            self.end_cloud_cover()

    def end_cloud_cover(self):
        """
        Immediately ends cloud cover
        """
        self.multiplier = 1.0
        self.cloud_duration = 0

    def tick(self):
        if self.cloud_duration > 0:
            self.cloud_duration -= 1
        else:
            self.multiplier = 1.0

        power = self.usageGenerator.get_reading_at(self.tick_count)
        if power is None:
            self.tick_count = 0
            power = self.usageGenerator.get_reading_at(self.tick_count)

        power *= self.multiplier

        # report power generated by PV
        self.log.info("Power generated by PV is : {}".format(power))


class FridgeAppliance(Appliance):

    def __init__(self, name: str = "Fridge", children: List["Area"] = None,
                 strategy: BaseStrategy = None):
        super().__init__(name, children, strategy)
        self.max_temp = 15.0
        self.min_temp = 5.0
        self.current_temp = 10.0
        self.heating_per_tick = 0.005
        self.cooling_per_tick = -.01
        self.temp_change_on_door_open = 5.0
        self.optimize_duration = 2                              # Optimize for these many markets/contracts in future

    def handle_door_open(self):
        """
        Do the following when fridge door is open
        1. Increase fridge temp
        2. If temp increases more than max allowed temp,
            2.a start cooling immediately
            2.b continue cooling until temp drops below max temp
            2.c stop cooling until next market cycle
        3. Else continue to run optimized schedule
        """
        self.log.warning("Fridge door was opened")
        self.current_temp += self.temp_change_on_door_open
        if self.current_temp > self.max_temp:
            self.change_mode_of_operation(ApplianceMode.ON)

    def tick(self):
        current_mode = self.mode
        temp_change = self.cooling_per_tick if current_mode == ApplianceMode.ON else self.heating_per_tick

        self.current_temp += temp_change

        if current_mode == ApplianceMode.ON:
            if self.tick_count <= 0:                                    # Optimized cycles are exhausted
                if self.min_temp <= self.current_temp <= self.max_temp:
                    self.change_mode_of_operation(ApplianceMode.OFF)    # temp is in range, stop cooling

                elif self.current_temp > self.max_temp:                 # Fridge is hot, continue cooling immaterial
                    self.usageGenerator.change_curve(self.energyCurve.get_mode_curve(ApplianceMode.ON))

                elif self.current_temp < self.min_temp:                 # Fridge is too cold, shut it down
                    self.change_mode_of_operation(ApplianceMode.OFF)

            else:                                       # continue running optimal cycles, fridge will eventually cool
                if self.current_temp < self.min_temp:                   # shutdown fridge if it is too cold
                    self.change_mode_of_operation(ApplianceMode.OFF)
        else:
            """
            If appliance is off, do the following
            1. If temp is high, fridge has to be powered on
                1.a If ticks are remaining, use the remaining optimal cycles
            2. If temp is in range, do nothing
            3. If temp is low, fridge is off anyways, temp will go down
            """
            if self.current_temp > self.max_temp:
                self.change_mode_of_operation(ApplianceMode.ON)  # Fridge is hot, cool it down
                if self.tick_count > 0:
                    # Load remaining optimal cycles into iterator.
                    self.log.debug("Load remaining optimal cycles into iterator.")

    def get_run_skip_cycle_counts(self, ticks_remaining : int):
        """
        Method to generate required and skip-able cycle counts within given remaining ticks.
        :param ticks_remaining: Number of ticks remaining before market cycles
        :return: tuple containing count of required cycles and skip-able cycles
        """
        mid = min((self.max_temp + self.min_temp)/2)
        diff = self.current_temp - mid
        cycles_required = 0
        cycles_skipped = 0
        ticks_per_cycle = len(self.energyCurve.get_mode_curve(ApplianceMode.ON))

        if diff < 0:
            """
            Current temp is lower than mid temp, bring temp up to mid temp
            calculate ticks remaining to optimize run cycles
            """

            t_h_mid = math.ceil((diff * -1)/self.heating_per_tick)
            ticks_remaining -= t_h_mid

        else:
            """
            current temp is above mid temp, bring temp to mid temp
            calculate cycles required to bring temp down to mid.
            calculate ticks required to run these cycles
            calculate ticks remaining
            """
            t_c_mid = math.ceil(diff/(self.cooling_per_tick * -1))
            ticks_remaining -= t_c_mid
            cycles_required += math.ceil(t_c_mid/ticks_per_cycle)

        """
        In remaining ticks, the temp can be allowed to rise to max before cooling is needed
        cycles needed to cool from max to mid are required # of cycles
        cycles needed to cool from mid to min are cycles that can be skipped.
        total cycles = required cycles + cycles that can be skipped
        """

        t_h_max = math.floor((self.max_temp - mid)/self.heating_per_tick)       # ticks to heat to max temp
        t_c_mid = math.ceil((self.max_temp - mid)/(self.cooling_per_tick * -1)) # ticks required to cool from max to mid
        t_range = t_h_max + t_c_mid     # ticks need to rise to max and cool back to mid
        quo = ticks_remaining // t_range    # num of times fridge can swing between mid and max
        rem = ticks_remaining % t_range     # remainder ticks to account for, shouldn't be more than 1
        extra = rem * t_range               # these ticks need to be accounted for

        cycles_required += math.ceil((quo * t_c_mid)/ticks_per_cycle)
        t_cooling_req = extra - t_h_max     # number of ticks cooling is absolutely needed from remaining extra ticks

        if t_cooling_req <= 0:   # temp will not rise beyond max in remaining time.
            cycles_skipped += math.floor(extra/ticks_per_cycle)     # use remaining time for cooling, but not required
        else:       # temp will rise above max, at least 1 cooling will be required
            extra_cooling_cycles = math.ceil(t_cooling_req/ticks_per_cycle)
            cycles_required += 1
            if extra_cooling_cycles > 1:
                cycles_skipped += extra_cooling_cycles - 1

        return cycles_required, cycles_skipped

    def _cycle_markets(self):
        super()._cycle_markets()
        bids = []
        count = self.optimize_duration
        for key in self.markets:
            bids.append(self.markets[key].avg_offer_price)
            count -= 1
            if count < 0:
                break

        ticks_per_bid = 15
        cycles = self.get_run_skip_cycle_counts(ticks_per_bid*self.optimize_duration)
        cycles_to_run = cycles[0]
        skip_cycles = cycles[1]

        schedule = RunSchedule(bids, self.energyCurve.get_mode_curve(ApplianceMode.ON),
                               ticks_per_bid, cycles_to_run, skip_cycles)

        schedule.calculate_running_cost()

