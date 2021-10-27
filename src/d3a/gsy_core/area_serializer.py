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
import json

from d3a.models.area import Area # NOQA
from d3a.models.strategy import BaseStrategy
from d3a.models.area.throughput_parameters import ThroughputParameters

from d3a.models.strategy.market_maker_strategy import MarketMakerStrategy  # NOQA
from d3a.models.strategy.commercial_producer import CommercialStrategy  # NOQA
from d3a.models.strategy.pv import PVStrategy  # NOQA
from d3a.models.strategy.storage import StorageStrategy  # NOQA
from d3a.models.strategy.load_hours import LoadHoursStrategy # NOQA
from d3a.models.strategy.predefined_load import DefinedLoadStrategy # NOQA
from d3a.models.strategy.predefined_pv import PVPredefinedStrategy, PVUserProfileStrategy  # NOQA
from d3a.models.strategy.finite_power_plant import FinitePowerPlant # NOQA

from d3a.models.leaves import Leaf # NOQA
from d3a.models.leaves import *  # NOQA
from d3a_interface.utils import convert_pendulum_to_str_in_dict, key_in_dict_and_not_none


class AreaEncoder(json.JSONEncoder):
    def default(self, obj):
        if type(obj) is Area:
            return self._encode_area(obj)
        elif isinstance(obj, Leaf):
            return self._encode_leaf(obj)
        elif isinstance(obj, BaseStrategy):
            return self._encode_subobject(obj)

    def _encode_area(self, area):
        result = {"name": area.name}
        if area.children:
            result['children'] = area.children
        if area.uuid:
            result['uuid'] = area.uuid
        if area.strategy:
            result['strategy'] = area.strategy
        if area.budget_keeper:
            result['budget_keeper'] = area.budget_keeper
        if area.display_type:
            result['display_type'] = area.display_type
        return result

    def _encode_subobject(self, obj):
        result = {"type": obj.__class__.__name__}
        kwargs = {key: getattr(obj, key) for key in getattr(obj, 'parameters', [])
                  if hasattr(obj, key)}
        if getattr(obj, 'non_attr_parameters', None):
            kwargs.update(obj.non_attr_parameters())
        if kwargs:
            kwargs = _convert_member_dt_to_string(kwargs)
            result['kwargs'] = kwargs
        return result

    def _encode_leaf(self, obj):
        description = {"name": obj.name,
                       "type": obj.__class__.__name__,
                       "display_type": obj.display_type}
        description.update(obj.parameters)
        description = _convert_member_dt_to_string(description)
        return description


def _convert_member_dt_to_string(in_dict):
    """
    Converts Datetime keys of members of in_dict into strings
    """
    for key, value in in_dict.items():
        if type(value) == dict:
            outdict = {}
            convert_pendulum_to_str_in_dict(value, outdict)
            in_dict[key] = outdict
    return in_dict


def area_to_string(area):
    """Create a json string representation of an Area"""
    return json.dumps(area, cls=AreaEncoder)


def _instance_from_dict(description):
    try:
        return globals()[description['type']](**description.get('kwargs', dict()))
    except Exception as exception:
        if 'type' in description and type(exception) is KeyError:
            raise ValueError("Unknown class '%s'" % description['type'])
        else:
            raise exception


def _leaf_from_dict(description, config):
    leaf_type = globals().get(description.pop('type'), type(None))
    if not issubclass(leaf_type, Leaf):
        raise ValueError("Unknown leaf type '%s'" % leaf_type)
    display_type = description.pop("display_type", None)
    leaf_object = leaf_type(**description, config=config)
    if display_type is not None:
        leaf_object.display_type = display_type
    return leaf_object


def area_from_dict(description, config):
    def optional(attr):
        return _instance_from_dict(description[attr]) if attr in description else None
    try:
        if 'type' in description:
            return _leaf_from_dict(description, config)  # Area is a Leaf
        name = description['name']
        uuid = description.get('uuid', None)
        external_connection_available = description.get('allow_external_connection', False)
        baseline_peak_energy_import_kWh = description.get('baseline_peak_energy_import_kWh', None)
        baseline_peak_energy_export_kWh = description.get('baseline_peak_energy_export_kWh', None)
        import_capacity_kVA = description.get('import_capacity_kVA', None)
        export_capacity_kVA = description.get('export_capacity_kVA', None)
        if key_in_dict_and_not_none(description, 'children'):
            children = [area_from_dict(child, config) for child in description['children']]
        else:
            children = None
        grid_fee_percentage = description.get('grid_fee_percentage', None)
        grid_fee_constant = description.get('grid_fee_constant', None)
        area = Area(name, children, uuid, optional('strategy'), config,
                    optional('budget_keeper'), grid_fee_percentage=grid_fee_percentage,
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
        raise ValueError("Input is not a valid area description (%s)" % str(error)) from error


def area_from_string(string, config):
    """Recover area from its json string representation"""
    return area_from_dict(json.loads(string), config)


def are_all_areas_unique(area, list_of_areas=set()):
    assert area.name not in list_of_areas
    list_of_areas.add(area.name)

    for child in area.children:
        list_of_areas = are_all_areas_unique(child, list_of_areas)

    return list_of_areas
