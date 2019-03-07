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
from d3a.models.budget_keeper import BudgetKeeper
from d3a.models.strategy import BaseStrategy
from d3a.models.appliance.simple import SimpleAppliance # NOQA

from d3a.models.appliance.inter_area import InterAreaAppliance  # NOQA
from d3a.models.appliance.pv import PVAppliance  # NOQA
from d3a.models.appliance.switchable import SwitchableAppliance # NOQA

from d3a.models.strategy.commercial_producer import CommercialStrategy  # NOQA
from d3a.models.strategy.pv import PVStrategy  # NOQA
from d3a.models.strategy.storage import StorageStrategy  # NOQA
from d3a.models.strategy.load_hours import LoadHoursStrategy, CellTowerLoadHoursStrategy # NOQA
from d3a.models.strategy.predefined_load import DefinedLoadStrategy # NOQA
from d3a.models.strategy.predefined_pv import PVPredefinedStrategy, PVUserProfileStrategy  # NOQA
from d3a.models.strategy.finite_power_plant import FinitePowerPlant # NOQA

from d3a.models.leaves import Leaf # NOQA
from d3a.models.leaves import *  # NOQA


class AreaEncoder(json.JSONEncoder):
    def default(self, obj):
        if type(obj) is Area:
            return self._encode_area(obj)
        elif isinstance(obj, Leaf):
            return self._encode_leaf(obj)
        elif isinstance(obj, (BaseStrategy, SimpleAppliance, BudgetKeeper)):
            return self._encode_subobject(obj)

    def _encode_area(self, area):
        result = {"name": area.name}
        if area.children:
            result['children'] = area.children
        if area.strategy:
            result['strategy'] = area.strategy
        if area.appliance:
            result['appliance'] = area.appliance
        if area.budget_keeper:
            result['budget_keeper'] = area.budget_keeper
        return result

    def _encode_subobject(self, obj):
        result = {"type": obj.__class__.__name__}
        kwargs = {key: getattr(obj, key) for key in getattr(obj, 'parameters', [])}
        if getattr(obj, 'non_attr_parameters', None):
            kwargs.update(obj.non_attr_parameters())
        if kwargs:
            result['kwargs'] = kwargs
        return result

    def _encode_leaf(self, obj):
        description = {"name": obj.name, "type": obj.__class__.__name__}
        description.update(obj.parameters)
        return description


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


def _leaf_from_dict(description):
    leaf_type = globals().get(description.pop('type'), type(None))
    if not issubclass(leaf_type, Leaf):
        raise ValueError("Unknown leaf type '%s'" % leaf_type)
    return leaf_type(**description)


def area_from_dict(description, config=None):
    def optional(attr):
        return _instance_from_dict(description[attr]) if attr in description else None
    try:
        if 'type' in description:
            return _leaf_from_dict(description)  # Area is a Leaf
        name = description['name']
        uuid = description['uuid']
        if 'children' in description:
            children = [area_from_dict(child) for child in description['children']]
        else:
            children = None
        return Area(name, uuid, children, optional('strategy'), optional('appliance'), config,
                    optional('budget_keeper'))
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        raise ValueError("Input is not a valid area description (%s)" % str(error))


def area_from_string(string, config=None):
    """Recover area from its json string representation"""
    return area_from_dict(json.loads(string), config)


def are_all_areas_unique(area, list_of_areas=set()):
    assert area.name not in list_of_areas
    list_of_areas.add(area.name)

    for child in area.children:
        list_of_areas = are_all_areas_unique(child, list_of_areas)

    return list_of_areas
