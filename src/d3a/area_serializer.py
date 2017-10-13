import json

from d3a.models.area import Area
from d3a.models.strategy.base import BaseStrategy
from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.appliance.appliance import Appliance

from d3a.models.appliance.fridge import FridgeAppliance  # NOQA
from d3a.models.appliance.inter_area import InterAreaAppliance  # NOQA
from d3a.models.appliance.pv import PVAppliance  # NOQA
from d3a.models.appliance.simple import SimpleAppliance  # NOQA

from d3a.models.strategy.commercial_producer import CommercialStrategy  # NOQA
from d3a.models.strategy.e_car import ECarStrategy  # NOQA
from d3a.models.strategy.fridge import FridgeStrategy  # NOQA
from d3a.models.strategy.greedy_night_storage import NightStorageStrategy  # NOQA
from d3a.models.strategy.heatpump import HeatPumpStrategy  # NOQA
from d3a.models.strategy.inter_area import InterAreaAgent  # NOQA
from d3a.models.strategy.permanent import PermanentLoadStrategy  # NOQA
from d3a.models.strategy.predef_load_household import PredefLoadHouseholdStrategy  # NOQA
from d3a.models.strategy.predef_load_prob import PredefLoadProbStrategy  # NOQA
from d3a.models.strategy.pv import PVStrategy  # NOQA
from d3a.models.strategy.simple import BuyStrategy, OfferStrategy  # NOQA
from d3a.models.strategy.storage import StorageStrategy  # NOQA


class AreaEncoder(json.JSONEncoder):
    def default(self, obj):
        if type(obj) is Area:
            return self._encode_area(obj)
        elif isinstance(obj, (BaseStrategy, SimpleAppliance, Appliance)):
            return self._encode_strategy_or_appliance(obj)

    def _encode_area(self, area):
        result = {"name": area.name}
        if area.children:
            result['children'] = area.children
        if area.strategy:
            result['strategy'] = area.strategy
        if area.appliance:
            result['appliance'] = area.appliance
        return result

    def _encode_strategy_or_appliance(self, obj):
        result = {"type": obj.__class__.__name__}
        kwargs = {key: getattr(obj, key) for key in getattr(obj, 'parameters', None)}
        if getattr(obj, 'non_attr_parameters', None):
            kwargs.update(obj.non_attr_parameters())
        if kwargs:
            result['kwargs'] = kwargs
        return result


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


def area_from_dict(description, config=None):
    try:
        name = description['name']
        if 'children' in description:
            children = [area_from_dict(child) for child in description['children']]
        else:
            children = None
        if 'strategy' in description:
            strategy = _instance_from_dict(description['strategy'])
        else:
            strategy = None
        if 'appliance' in description:
            appliance = _instance_from_dict(description['appliance'])
        else:
            appliance = None
        return Area(name, children, strategy, appliance, config)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        raise ValueError("Input is not a valid area description (%s)" % str(error))


def area_from_string(string, config=None):
    """Recover area from its json string representation"""
    return area_from_dict(json.loads(string), config)
