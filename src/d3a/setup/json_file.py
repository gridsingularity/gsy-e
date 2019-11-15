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
import os
from d3a.d3a_core.area_serializer import area_from_string


def get_setup(config):
    try:
        setup_path = os.environ['D3A_SETUP_PATH']
        with open(setup_path, 'r') as area_file:
            area_str = area_file.read().replace('\n', '')
        recovered_area = area_from_string(area_str)
        recovered_area._config = config
        return recovered_area
    except KeyError as d3a_key_error:
        raise RuntimeError('D3_SETUP_PATH environment variable not found.') from d3a_key_error
    except FileNotFoundError as d3a_file_error:
        raise RuntimeError('D3A setup file containing area not found on the D3_SETUP_PATH') \
            from d3a_file_error


if __name__ == "__main__":
    get_setup(None)
