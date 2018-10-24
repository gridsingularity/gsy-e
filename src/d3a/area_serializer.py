import json

from d3a.models.area import Area # NOQA
from d3a.models.budget_keeper import BudgetKeeper
from d3a.models.strategy.base import BaseStrategy
from d3a.models.appliance.simple import SimpleAppliance # NOQA
from d3a.models.appliance.appliance import Appliance

from d3a.models.appliance.fridge import FridgeAppliance  # NOQA
from d3a.models.appliance.inter_area import InterAreaAppliance  # NOQA
from d3a.models.appliance.pv import PVAppliance  # NOQA
from d3a.models.appliance.switchable import SwitchableAppliance # NOQA

from d3a.models.strategy.commercial_producer import CommercialStrategy  # NOQA
from d3a.models.strategy.e_car import ECarStrategy  # NOQA
from d3a.models.strategy.fridge import FridgeStrategy  # NOQA
from d3a.models.strategy.heatpump import HeatPumpStrategy  # NOQA
from d3a.models.strategy.inter_area import InterAreaAgent  # NOQA
from d3a.models.strategy.permanent import PermanentLoadStrategy  # NOQA
from d3a.models.strategy.predef_load_household import PredefLoadHouseholdStrategy  # NOQA
from d3a.models.strategy.predef_load_prob import PredefLoadProbStrategy  # NOQA
from d3a.models.strategy.pv import PVStrategy  # NOQA
from d3a.models.strategy.simple import BuyStrategy, OfferStrategy  # NOQA
from d3a.models.strategy.storage import StorageStrategy  # NOQA
from d3a.models.strategy.load_hours_fb import LoadHoursStrategy, CellTowerLoadHoursStrategy # NOQA
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
        elif isinstance(obj, (BaseStrategy, SimpleAppliance, Appliance, BudgetKeeper)):
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
        if 'children' in description:
            children = [area_from_dict(child) for child in description['children']]
        else:
            children = None
        return Area(name, children, optional('strategy'), optional('appliance'), config,
                    optional('budget_keeper'))
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        raise ValueError("Input is not a valid area description (%s)" % str(error))


def area_from_string(string, config=None):
    """Recover area from its json string representation"""
    return area_from_dict(json.loads(string), config)
