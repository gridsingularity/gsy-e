from d3a.models.area import Area
from d3a.models.strategy.base import BaseStrategy
from typing import List
from enum import Enum
from d3a.models.resource.properties import ApplianceProperties, ElectricalProperties, MeasurementParamType
from logging import getLogger
from d3a.util import TaggedLogWrapper
import random


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


class Appliance(Area):

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

    def tick(self):
        """
        Handle pendulum ticks
        """
        super().tick()
        usage = self.get_usage_reading()
        self.log.debug("Appliance {} usage: {}".format(usage[0], usage[1]))
        self.historicUsageCurve[self.get_now()] = usage

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
