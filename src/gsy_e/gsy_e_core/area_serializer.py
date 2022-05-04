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
import json

from gsy_framework.utils import convert_pendulum_to_str_in_dict, key_in_dict_and_not_none

from gsy_e.models.area import Area # NOQA
from gsy_e.models.strategy import BaseStrategy
from gsy_e.models.area.throughput_parameters import ThroughputParameters

from gsy_e.models.leaves import Leaf # NOQA
from gsy_e.models.leaves import *  # NOQA  pylint: disable=wildcard-import, unused-wildcard-import


class AreaEncoder(json.JSONEncoder):
    """Json encoder for Area object."""

    def default(self, o):
        if type(o) is Area:  # pylint: disable=unidiomatic-typecheck
            return self._encode_area(o)
        if isinstance(o, Leaf):
            return self._encode_leaf(o)
        if isinstance(o, BaseStrategy):
            return self._encode_subobject(o)
        return None

    @staticmethod
    def _encode_area(area):
        result = {"name": area.name}
        if area.children:
            result["children"] = area.children
        if area.uuid:
            result["uuid"] = area.uuid
        if area.strategy:
            result["strategy"] = area.strategy
        if area.display_type:
            result["display_type"] = area.display_type
        return result

    @staticmethod
    def _encode_subobject(obj):
        result = {"type": obj.__class__.__name__}
        kwargs = {key: getattr(obj, key) for key in getattr(obj, "parameters", [])
                  if hasattr(obj, key)}
        if kwargs:
            kwargs = _convert_member_dt_to_string(kwargs)
            result["kwargs"] = kwargs
        return result

    @staticmethod
    def _encode_leaf(obj):
        description = {"name": obj.name,
                       "type": obj.__class__.__name__,
                       "display_type": obj.display_type}
        description.update(obj.parameters)
        description = _convert_member_dt_to_string(description)
        return description


def _convert_member_dt_to_string(in_dict):
    """
    Converts Datetime keys of members of in_dict into strings.
    """
    for key, value in in_dict.items():
        if isinstance(value, dict):
            outdict = {}
            convert_pendulum_to_str_in_dict(value, outdict)
            in_dict[key] = outdict
    return in_dict


def area_to_string(area):
    """Create a json string representation of an Area."""
    return json.dumps(area, cls=AreaEncoder)


def _instance_from_dict(description):
    try:
        return globals()[description["type"]](**description.get("kwargs", {}))
    # pylint: disable=broad-except
    except Exception as exception:
        if "type" in description and isinstance(exception, KeyError):
            raise ValueError(f"Unknown class '{description['type']}'") from exception
        raise exception


def _leaf_from_dict(description, config):
    leaf_type = globals().get(description.pop("type"), type(None))
    if not issubclass(leaf_type, Leaf):
        raise ValueError(f"Unknown leaf type '{leaf_type}'")
    display_type = description.pop("display_type", None)
    leaf_object = leaf_type(**description, config=config)
    if display_type is not None:
        leaf_object.display_type = display_type
    return leaf_object


def area_from_dict(description, config):
    """Return an Area object based on representation dict."""
    def optional(attr):
        return _instance_from_dict(description[attr]) if attr in description else None
    try:
        if "type" in description:
            return _leaf_from_dict(description, config)  # Area is a Leaf
        name = description["name"]
        uuid = description.get("uuid", None)
        external_connection_available = description.get("allow_external_connection", False)
        baseline_peak_energy_import_kWh = description.get("baseline_peak_energy_import_kWh", None)
        baseline_peak_energy_export_kWh = description.get("baseline_peak_energy_export_kWh", None)
        import_capacity_kVA = description.get("import_capacity_kVA", None)
        export_capacity_kVA = description.get("export_capacity_kVA", None)
        if key_in_dict_and_not_none(description, "children"):
            children = [area_from_dict(child, config) for child in description["children"]]
        else:
            children = []
        grid_fee_percentage = description.get("grid_fee_percentage", None)
        grid_fee_constant = description.get("grid_fee_constant", None)
        area = Area(name, children, uuid, optional("strategy"), config,
                    grid_fee_percentage=grid_fee_percentage,
                    grid_fee_constant=grid_fee_constant,
                    external_connection_available=external_connection_available and
                    config.external_connection_enabled,
                    throughput=ThroughputParameters(
                        baseline_peak_energy_import_kWh=baseline_peak_energy_import_kWh,
                        baseline_peak_energy_export_kWh=baseline_peak_energy_export_kWh,
                        import_capacity_kVA=import_capacity_kVA,
                        export_capacity_kVA=export_capacity_kVA)
                    )
        if "display_type" in description:
            area.display_type = description["display_type"]
        return area
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        raise ValueError(f"Input is not a valid area description ({str(error)})") from error


def area_from_string(string, config):
    """Recover area from its json string representation."""
    return area_from_dict(json.loads(string), config)


def are_all_areas_unique(area, list_of_areas=set()):  # pylint: disable=dangerous-default-value
    """Check if area name is unique."""
    assert area.name not in list_of_areas
    list_of_areas.add(area.name)

    for child in area.children:
        list_of_areas = are_all_areas_unique(child, list_of_areas)

    return list_of_areas
