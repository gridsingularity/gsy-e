"""
Copyright 2018 Grid Singularity
This file is part of Grid Singularity Exchange.

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
from gsy_e.gsy_e_core.area_serializer import area_from_dict
import json
import os.path as osp
dir_path = osp.dirname(osp.realpath(__file__))
json_area_location = osp.join(dir_path, '..', "resources", "area.json")


def get_setup(config):
    try:
        with open(json_area_location,'r') as f:
            area_description = json.load(f)
        return area_from_dict(area_description, config)
    except AttributeError as ex:
        raise RuntimeError("Area not found") from ex


def create_area_json():
    from gsy_e.gsy_e_core.area_serializer import area_to_string
    # 
    from gsy_e.setup.bc4p.demonstration import get_setup as get_demo_setup
    from gsy_e.models.config import create_simulation_config_from_global_config
    config = create_simulation_config_from_global_config()
    dir_path = osp.dirname(osp.realpath(__file__))
    json_area_location = osp.join(dir_path, '..', "resources", "area.json")
    area = get_demo_setup(config)
    with open(json_area_location, 'w') as f:
        j = json.loads(area_to_string(area))
        json.dump(j, f, indent=4)
