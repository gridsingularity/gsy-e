from d3a.simulation import Simulation
from d3a.util import IntervalType
from d3a.models.strategy.predefined_pv import d3a_path
import os


def test_parse_settings_file():
    simulation = Simulation(setup_module_name="default",
                            settings_file=os.path.join(d3a_path, "setup", "d3a-settings.json"))
    assert simulation.advanced_settings["DEFAULT_RISK"] == 50
    assert simulation.simulation_config.__getattribute__("duration") == IntervalType('H:M')("24h")
