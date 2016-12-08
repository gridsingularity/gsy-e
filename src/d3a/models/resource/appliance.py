from d3a.models.area import Area
from d3a.models.strategy.base import BaseStrategy
from typing import List
from enum import Enum
from d3a.models.resource.properties import ApplianceProperties, ElectricalProperties, MeasurementParamType
from logging import getLogger
from d3a.util import TaggedLogWrapper
from d3a.models.strategy.simple import OfferStrategy


log = getLogger(__name__)


class ApplianceMode(Enum):
    ON = 1
    OFF = 2


class EnergyProfile:

    def __init__(self, mode: ApplianceMode=ApplianceMode.ON):
        self.operationMode = mode
        self.dataset = []

    def get_appliance_mode(self) -> ApplianceMode:
        return self.operationMode

    def get_mode_profile(self):
        return self.dataset

    def get_usage(self):
        while True:
            for usage in self.dataset:
                yield usage


class UsageGenerator:
    def __init__(self, profiles):
        self.mode = None
        self.changed = True
        self.profileDict = profiles
        self.dataset = None
        self.log = TaggedLogWrapper(log, UsageGenerator.__name__)

    def iterator(self):
        while True:
            for data in self.dataset:
                yield data

    def change_mode(self, newmode: ApplianceMode):
        """
        Change mode of operation for appliance
        :param newmode: New mode of operation
        :return: iterator containing usage profile
        """
        iterator = None
        if newmode in self.profileDict:
            self.mode = newmode
            self.changed = True
            self.dataset = self.profileDict[newmode]
            iterator = self.iterator()
            self.log.info("New mode of operation is {}".format(newmode))
        else:
            self.log.warning("Usage profile not defined for mode: {}".format(newmode))

        return iterator


class Appliance(Area):

    def __init__(self, name: str = None, children: List["Area"] = None,
                 strategy: BaseStrategy = None):
        super().__init__(name, children, strategy)

        self.applianceProfile = None
        self.electricalProperties = None
        self.dictModePattern = dict()
        self.mode = ApplianceMode.ON if self.active is True else ApplianceMode.OFF
        self.usageGenerator = UsageGenerator(self.dictModePattern)
        self.iterator = self.usageGenerator.iterator()
        self.measuring = MeasurementParamType.POWER

        self.log.debug("Appliance instantiated, current state {}, mode {}".format(self.active, self.mode))

    def set_appliance_properties(self, properties: ApplianceProperties):
        """
        Provide appliance profile details
        :param properties:
        """
        self.applianceProfile = properties
        self.log.debug("Updated appliance properties")

    def set_electrical_properties(self, electrical: ElectricalProperties):
        """
        Provide elecrtrical properties
        :param electrical:
        """
        self.electricalProperties = electrical
        self.log.debug("Updated electrical properties")

    def define_usage_for_mode(self, mode: ApplianceMode, pattern: List = []):
        self.dictModePattern[mode] = pattern

    def change_mode_of_operation(self, newmode: ApplianceMode):
        if newmode is not None:
            if newmode != self.mode:
                self.iterator = self.usageGenerator.change_mode(newmode)
                self.log.info("Appliance mode changed to: {}".format(newmode))
            else:
                self.log.warning("NOOP, Appliance already in mode: {}".format(newmode))
        else:
            self.log.error("New mode not recognized")

    def tick(self):
        """
        Handle pendulum ticks
        """
        super().tick()
        self.log.debug("Appliance {} usage: {}".format(self.measuring, self.iterator.next()))


class PVAppliance(Appliance):

    def __init__(self, name: str = "PV", children: List["Area"] = None,
                 strategy: BaseStrategy = None):
        super().__init__(name, children, strategy)
