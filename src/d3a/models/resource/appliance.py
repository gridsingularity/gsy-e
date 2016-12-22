from d3a.models.area import Area
from typing import List
from enum import Enum
from d3a.models.resource.properties import ApplianceProperties, ElectricalProperties, MeasurementParamType
from logging import getLogger
import random
from d3a.models.resource.run_algo import RunSchedule
import math
from d3a.models.appliance.base import BaseAppliance
from d3a.models.area import DEFAULT_CONFIG


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

    def iterator(self):
        while True:
            for data in self.curve:
                yield data

    def randomize_usage_pattern(self, curve: List):
        randomized = []
        for index in range(0, len(curve)):
            randomized.append(float(curve[index]) + random.uniform(self.minVariance, self.maxVariance))

        return randomized

    def change_curve(self, curve: List, randomize: bool = False):
        self.curve = self.randomize_usage_pattern(curve) if randomize else curve
        return self.iterator()

    def get_reading_at(self, index: int):
        val = None
        if index < 0 or index >= len(self.curve):
            val = self.curve[index]

        return val


class Appliance(BaseAppliance):

    def __init__(self, name: str):
        super().__init__()
        self.name = name
        self.applianceProfile = None
        self.electricalProperties = None
        self.energyCurve = None
        self.mode = ApplianceMode.OFF
        self.usageGenerator = None
        self.iterator = None
        self.measuring = MeasurementParamType.POWER
        # self.historicUsageCurve = dict()
        self.bids = []
        self.tick_count = 0              # count to keep track of ticks since past

        log.debug("Appliance instantiated, current mode of operation is {}".format(self.mode))

    def start_appliance(self):
        log.info("Starting appliance {}".format(self.name))

        if self.electricalProperties is not None:
            self.usageGenerator = UsageGenerator([],
                                                 self.electricalProperties.get_min_variance(),
                                                 self.electricalProperties.get_max_variance())
        else:
            log.error("Appliance electrical properties not set")
            return

        if self.energyCurve is not None:
            if self.energyCurve.get_mode_curve(ApplianceMode.ON) is not None:
                self.change_mode_of_operation(ApplianceMode.ON)
            else:
                self.mode = ApplianceMode.OFF
                log.error("Power ON energy curve is not defined for appliance")
        else:
            log.error("Energy curves not defined for operation modes")
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
        log.debug("Updated appliance properties")

    def set_electrical_properties(self, electrical: ElectricalProperties):
        """
        Provide electrical properties
        :param electrical:
        """
        self.electricalProperties = electrical
        log.debug("Updated electrical properties")

    def change_mode_of_operation(self, newmode: ApplianceMode):
        if self.usageGenerator is not None:
            if newmode is not None:
                if newmode != self.mode:
                    self.iterator = self.usageGenerator.change_curve(self.energyCurve.get_mode_curve(newmode), True)
                    self.mode = newmode
                    log.info("Appliance mode changed to: {}".format(newmode))
                else:
                    log.warning("NOOP, Appliance already in mode: {}".format(newmode))
            else:
                log.error("New mode not recognized")
        else:
            log.error("Usage generator uninitialized")

    def tick(self):
        """
        Handle pendulum ticks
        """
        usage = self.get_usage_reading()
        log.debug("Appliance {} usage: {}".format(usage[0], usage[1]))
        # self.historicUsageCurve[self.get_now()] = usage

    def event_tick(self, *, area: Area):
        if not self.owner:
            # Should not happen
            return
        market = area.current_market
        if not market:
            # No current market yet
            return
        # Fetch traded energy for `market`
        energy = self.owner.strategy.energy_balance(market)
        if energy:
            area.report_accounting(market, self.owner.name, energy / area.config.ticks_per_slot)

    def event_market_cycle(self):
        pass

    def get_historic_usage_curve(self):
        # return self.historicUsageCurve
        return None

    def get_measurement_param(self) -> MeasurementParamType:
        return self.measuring

    def get_usage_reading(self) -> tuple:
        return self.measuring, self.iterator.__next__()

    def update_iterator(self, curve, randomize: bool = False):
        """
        Method to update the curve used by iterator
        :param curve: new curve to be used
        :param randomize: Randomize the curve before updating
        """
        self.iterator = self.usageGenerator.change_curve(curve, randomize)

    def is_appliance_consuming_energy(self):
        """
        Check if appliance is consuming energy
        :return: True if power is being consumed, else false
        """
        running = False
        if self.usageGenerator.get_reading_at(self.tick_count) > 0:
            running = True

        return running


class PVAppliance(Appliance):

    def __init__(self, name: str = "PV"):
        super().__init__(name)
        self.cloud_duration = 0
        self.multiplier = 1.0

    def handle_cloud_cover(self, percent: float = 0, duration: int = 0):
        """
        Method to introduce cloud cover over PV. PV will produce 0 W during cloud cover.
        :param percent: Cloud cover between 0 - 100%.
        :param duration: duration of cloud cover in ticks.
        """
        self.cloud_duration = duration
        # 2% residual power generated even under 100% cloud cover
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

        power = self.iterator.__next__()
        if power is None:
            # power = self.usageGenerator.get_reading_at(self.tick_count)
            power = 0

        power *= self.multiplier

        # report power generated by PV
        log.info("Power generated by PV is : {}".format(power))
        self.tick_count += 1


class FridgeAppliance(Appliance):

    def __init__(self, name: str = "Fridge"):
        super().__init__(name)
        self.max_temp = 15.0
        self.min_temp = 5.0
        self.current_temp = 10.0
        self.heating_per_tick = 0.005
        self.cooling_per_tick = -.01
        self.temp_change_on_door_open = 5.0
        self.optimize_duration = 1                              # Optimize for these many markets/contracts in future
        self.duration = 0
        self.force_cool_ticks = 0

    def handle_door_open(self, duration: int):
        """
        :param duration: number of ticks door will be open for
        Do the following when fridge door is open
        1. Increase fridge temp
        2. If temp increases more than max allowed temp,
            2.a start cooling immediately
            2.b continue cooling until temp drops below max temp
            2.c Optimize running for remaining time in current market cycle.
        3. Else continue to run optimized schedule
        """
        log.warning("Fridge door was opened")
        self.duration = duration
        self.current_temp += self.temp_change_on_door_open

    def tick(self):
        if self.duration > 0:
            log.warning("Fridge door is still open")
            self.duration -= 1
            self.current_temp += self.temp_change_on_door_open

        if self.current_temp > self.max_temp:                       # Fridge is hot, start cooling immediately
            self.update_force_cool_ticks()
            if self.mode == ApplianceMode.OFF:
                self.change_mode_of_operation(ApplianceMode.ON)
            else:
                self.update_iterator(self.energyCurve.get_mode_curve(ApplianceMode.ON))
        elif self.current_temp < self.min_temp:                     # Fridge is too cold
            if self.mode == ApplianceMode.ON:
                self.change_mode_of_operation(ApplianceMode.OFF)
        else:                                                       # Fridge is in acceptable temp range
            if self.mode == ApplianceMode.OFF:
                self.change_mode_of_operation(ApplianceMode.ON)
                self.update_iterator(self.gen_run_schedule())

            if self.is_appliance_consuming_energy():
                self.current_temp += self.cooling_per_tick
            else:
                self.current_temp += self.heating_per_tick

        # Fridge is being force cooled
        if self.force_cool_ticks > 0:
            self.force_cool_ticks -= 1
            if self.force_cool_ticks <= 0:
                # This is last force cool tick, optimize remaining ticks
                self.update_iterator(self.gen_run_schedule())

        self.tick_count += 1

    def update_force_cool_ticks(self):
        """
        Temp of fridge is high, update the number of ticks it will take to bring down the temp of fridge just below
        allowed max temp.
        :param self:
        :return:
        """
        diff = self.current_temp - self.max_temp
        ticks_per_cycle = len(self.energyCurve.get_mode_curve(ApplianceMode.ON))
        temp_drop_per_cycle = self.cooling_per_tick * ticks_per_cycle
        cycles_to_run = math.ceil(diff/temp_drop_per_cycle)
        self.force_cool_ticks = cycles_to_run * ticks_per_cycle
        log.warning("It will take fridge {} ticks to cool.".format(self.force_cool_ticks))

    def get_run_skip_cycle_counts(self, ticks_remaining: int):
        """
        Method to generate required and skip-able cycle counts within given remaining ticks.
        :param ticks_remaining: Number of ticks remaining before market cycles
        :return: tuple containing count of required cycles and skip-able cycles
        """
        mid = math.floor((self.max_temp + self.min_temp)/2)
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
        # ticks required to cool from max to mid
        t_c_mid = math.ceil((self.max_temp - mid)/(self.cooling_per_tick * -1))
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

    def gen_run_schedule(self):
        ticks_remaining = DEFAULT_CONFIG.ticks_per_slot * self.optimize_duration - self.tick_count
        cycles = self.get_run_skip_cycle_counts(ticks_remaining)
        cycles_to_run = cycles[0]
        skip_cycles = cycles[1]
        schedule = None

        if self.bids:
            run_schedule = RunSchedule(self.bids, self.energyCurve.get_mode_curve(ApplianceMode.ON),
                                       DEFAULT_CONFIG.ticks_per_slot, cycles_to_run, skip_cycles, self.tick_count)
            schedule = run_schedule.get_run_schedule()

        return schedule

    def event_market_cycle(self):
        super().event_market_cycle()
        self.bids = []
        # count = self.optimize_duration
        # for key in self.markets:
        #     self.bids.append(self.markets[key].avg_offer_price)
        #     count -= 1
        #     if count < 0:
        #         break

        self.tick_count = 0
        self.change_mode_of_operation(ApplianceMode.ON)
        self.update_iterator(self.gen_run_schedule())
