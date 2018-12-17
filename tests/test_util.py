"""
Copyright 2018 Grid Singularity
This file is part of D3A.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
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
