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
from d3a.d3a_core.area_serializer import area_from_dict
import d3a.constants


def get_setup(config):
    try:
        area_description = config.area
        if "collaboration_uuid" in area_description:
            d3a.constants.COLLABORATION_ID = area_description.pop("collaboration_uuid")
            d3a.constants.EXTERNAL_CONNECTION_WEB = True
        return area_from_dict(area_description, config)
    except AttributeError as ex:
        raise RuntimeError('Area not found') from ex
