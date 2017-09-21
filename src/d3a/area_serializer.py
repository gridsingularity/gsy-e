import json

from d3a.models.area import Area
from d3a.models.strategy.base import BaseStrategy
from d3a.models.appliance.simple import SimpleAppliance

from d3a.models.appliance.fridge import FridgeAppliance  # NOQA

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
        elif isinstance(obj, BaseStrategy):
            return self._encode_strategy(obj)
        elif isinstance(obj, SimpleAppliance):
            return self._encode_appliance(obj)

    def _encode_area(self, area):
        result = {"name": area.name}
        if area.children:
            result['children'] = area.children
        if area.strategy:
            result['strategy'] = area.strategy
        if area.appliance:
            result['appliance'] = area.appliance
        return result

    def _encode_strategy(self, strategy):
        result = {"type": strategy.__class__.__name__}
        result['params'] = strategy.non_attr_parameters()
        if strategy.parameters:
            for p in strategy.parameters:
                result['params'][p] = getattr(strategy, p)
        return result

    def _encode_appliance(self, appliance):
        result = {"type": appliance.__class__.__name__}
        return result


def area_to_string(area):
    """Create a json string representation of an Area"""
    return json.dumps(area, cls=AreaEncoder)


def _instance_from_dict(description):
    params = description['params'] if 'params' in description else dict()
    try:
        return globals()[description['type']](**params)
    except Exception as exception:
        if 'type' in description and type(exception) is KeyError:
            raise ValueError("Unknown class '%s'" % description['type'])
        else:
            raise exception


def area_from_dict(description):
    try:
        name = description['name']
        if 'children' in description:
            children = list()
            for child in description['children']:
                children.append(area_from_dict(child))
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
        return Area(name, children, strategy, appliance)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        raise ValueError("Input is not a valid area description (%s)" % str(error))


def area_from_string(string):
    """Recover area from its json string representation"""
    return area_from_dict(json.loads(string))
