from typing import List
from enum import Enum
from d3a.models.appliance.properties import MeasurementParamType
from logging import getLogger
from d3a.models.appliance.base import BaseAppliance
from d3a.models.area import Area
from pendulum import Interval
import math
import random

from d3a.models.events import Trigger


log = getLogger(__name__)


class ApplianceMode(Enum):
    ON = 1
    OFF = 2
    IDLE = 3


class EnergyCurve:

    def __init__(self, mode: ApplianceMode, curve: List,
                 sampling: Interval, tick_duration: Interval):
        self.dictModeCurve = dict()
        self.sampling = sampling
        self.tick_duration = tick_duration
        self.add_mode_curve(mode, curve)

    def get_mode_curve(self, mode: ApplianceMode):
        return self.dictModeCurve[mode]

    def add_mode_curve(self, mode: ApplianceMode, curve: List):
        sample_rate_diff = self.sampling.in_seconds() - self.tick_duration.in_seconds()
        effective_curve = curve
        if sample_rate_diff == 0:
            # Sample rate is same as tick frequency
            # print("Sample rates are same")
            pass
        elif sample_rate_diff < 0:
            # Sample rate is more than tick frequency, scale it down to tick frequency
            # print("Interglot the provided curve")
            divider = int(math.ceil(self.tick_duration.in_seconds()/self.sampling.in_seconds()))
            effective_curve = EnergyCurve.interglot_curve(curve, divider)
        else:
            # Sample rate is less than tick freq, over sample the samples to match tick rate
            # print("Over sample the provided curve")
            multiplier = int(math.ceil(self.sampling.in_seconds()/self.tick_duration.in_seconds()))
            effective_curve = EnergyCurve.over_sample_curve(curve, multiplier)

        # print("Length of effective curve: {}".format(len(effective_curve)))
        self.dictModeCurve[mode] = effective_curve

    @staticmethod
    def over_sample_curve(curve: List, multiplier: int = 1):
        new_curve = []
        for sample in curve:
            for i in range(0, multiplier):
                new_curve.append(sample / multiplier)

        return new_curve

    @staticmethod
    def interglot_curve(curve: List, divider: int = 1):
        new_curve = []
        index = 0
        while index < len(curve):
            new_curve.append(curve[index])
            index += divider

        return new_curve


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
            randomized.append(float(curve[index]) +
                              random.uniform(self.minVariance, self.maxVariance))

        return randomized

    def change_curve(self, curve: List, randomize: bool = False):
        self.curve = self.randomize_usage_pattern(curve) if randomize else curve
        return self.iterator()

    def get_reading_at(self, index: int):
        if index > 0:
            index %= len(self.curve)

        return None if index < 0 else self.curve[index]


class Appliance(BaseAppliance):
    available_triggers = [
        Trigger('on', state_getter=lambda s: s.mode == ApplianceMode.ON,
                help="Turn appliance on. Starts consuming energy."),
        Trigger('off', state_getter=lambda s: s.mode == ApplianceMode.OFF,
                help="Turn appliance off. Stops consuming energy.")
    ]

    def __init__(self, name: str, report_freq: int = 1):
        """
        Initialize base Appliance class
        :param name: name of the appliance
        :param report_freq: Report power usage/generation after these many ticks
        """
        super().__init__()
        self.name = name
        self.electrical_properties = None
        self.energy_curve = None
        self.mode = ApplianceMode.OFF
        self.usageGenerator = None
        self.iterator = None
        self.measuring = MeasurementParamType.POWER
        self.report_frequency = report_freq
        self.last_reported_tick = self.report_frequency
        self.report_sign = -1   # Consumption of power is reported as -ve and prod is +ve

        log.debug("Appliance instantiated, current mode of operation is {}".format(self.mode))

    def start_appliance(self):
        log.info("Starting appliance {}".format(self.name))

        if self.electrical_properties is not None:
            self.usageGenerator = UsageGenerator([],
                                                 self.electrical_properties.get_min_variance(),
                                                 self.electrical_properties.get_max_variance())
        else:
            log.error("Appliance electrical properties not set")
            return

        if self.energy_curve is not None:
            if self.energy_curve.get_mode_curve(ApplianceMode.ON) is not None:
                self.change_mode_of_operation(ApplianceMode.ON)
            else:
                self.mode = ApplianceMode.OFF
                log.error("Power ON energy curve is not defined for appliance")
        else:
            log.error("Energy curves not defined for operation modes")
            return

    def change_mode_of_operation(self, newmode: ApplianceMode):
        if self.usageGenerator is not None:
            if newmode is not None:
                if newmode != self.mode:
                    self.iterator = self.usageGenerator.change_curve(
                        self.energy_curve.get_mode_curve(newmode), True)
                    self.mode = newmode
                    log.info("Appliance mode changed to: {}".format(newmode))
                else:
                    log.warning("NOOP, Appliance already in mode: {}".format(newmode))
            else:
                log.error("New mode not recognized")
        else:
            log.error("Usage generator uninitialized")

    def event_tick(self, *, area: Area):

        if area is None:
            return

        if self.last_reported_tick == self.report_frequency:
            # report power generation/consumption to area
            self.last_reported_tick = 0
            # Fetch traded energy for `market`
            self.report_energy(area, self.get_current_power())

        self.last_reported_tick += 1

    def report_energy(self, area: Area, energy: float):
        market = area.current_market
        if energy:
            # Convert energy to KWh, divide by 1000
            area.report_accounting(market, self.owner.name, energy * self.report_sign)

    def get_current_power(self):
        return self.iterator.__next__()

    def event_market_cycle(self):
        pass

    def get_measurement_param(self) -> MeasurementParamType:
        return self.measuring

    def get_usage_reading(self) -> tuple:
        return self.measuring, self.get_current_power()

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
        if self.usageGenerator.get_reading_at(self.get_tick_count()) > 0:
            running = True

        return running

    def get_energy_balance(self) -> int:
        # -ve energy is energy bought
        return self.owner.strategy.energy_balance(self.area.current_market)

    def get_tick_energy_balance(self, report_freqency=1):
        return self.get_energy_balance() / (self.area.config.ticks_per_slot / report_freqency)

    def get_tick_count(self):
        return self.area.current_tick % self.area.config.ticks_per_slot

    def get_time_in_sec(self):
        return (self.area.current_tick * self.area.config.tick_length).in_seconds()

    def trigger_on(self):
        self.change_mode_of_operation(ApplianceMode.ON)

    def trigger_off(self):
        self.change_mode_of_operation(ApplianceMode.OFF)
