from d3a.d3a_core.util import available_simulation_scenarios
from d3a import setup as d3a_setup
import os


def test_validate_all_setup_scenarios_are_available():
    file_list = []
    root_path = d3a_setup.__path__[0] + '/'
    for path, _, files in os.walk(root_path):
        for name in files:
            if name.endswith(".py") and name != "__init__.py":
                module_name = os.path.join(path, name[:-3]).\
                    replace(root_path, '').replace("/", ".")
                file_list.append(module_name)
    assert set(file_list) == set(available_simulation_scenarios)
