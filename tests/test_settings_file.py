import os
import unittest

from d3a.util import IntervalType
from d3a.util import d3a_path
from d3a.models.strategy.const import ConstSettings
from d3a.util import read_settings_from_file
from d3a.util import update_advanced_settings
from d3a.models.config import SimulationConfig


class SampleTest(unittest.TestCase):
    def test_parse_settings_file(self):
        simulation_settings, advanced_settings = read_settings_from_file(
            os.path.join(d3a_path, "setup", "d3a-settings.json"))
        update_advanced_settings(advanced_settings)
        simulation_config = SimulationConfig(**simulation_settings)

        assert simulation_config.__getattribute__("duration") == IntervalType('H:M')("24h")
        try:
            for setting in advanced_settings.keys():
                getattr(ConstSettings, setting)
        except AttributeError:
            self.fail("The settings file is not consistent with the selection of variables in "
                      "const.py")
