import os
import unittest

from d3a.simulation import Simulation
from d3a.util import IntervalType
from d3a.models.strategy.predefined_pv import d3a_path
from d3a.models.strategy.const import ConstSettings


class SampleTest(unittest.TestCase):
    def test_parse_settings_file(self):

        simulation = Simulation(setup_module_name="default",
                                settings_file=os.path.join(d3a_path, "setup", "d3a-settings.json"))
        assert \
            simulation.simulation_config.__getattribute__("duration") == IntervalType('H:M')("24h")
        try:
            for setting in simulation.advanced_settings.keys():
                getattr(ConstSettings, setting)
        except AttributeError:
            self.fail("The settings file is not consistent with the selection of variables in "
                      "const.py")
