import json

from d3a.models.area import Area


class AreaEncoder(json.JSONEncoder):
    def default(self, obj):
        if type(obj) is Area:
            return self._encode_area(obj)

    def _encode_area(self, area):
        result = {"name": area.name}
        if area.children:
            result['children'] = area.children
        if area.strategy:
            result['strategy'] = area.strategy
        if area.appliance:
            result['appliance'] = area.appliance
        return result


def area_to_string(area):
    """Create a json string representation of an Area"""
    return json.dumps(area, cls=AreaEncoder)


def area_from_dict(description):
    try:
        name = description['name']
        if 'children' in description:
            children = list()
            for child in description['children']:
                children.append(area_from_dict(child))
        else:
            children = None
        strategy = None  # TODO
        appliance = None  # TODO
        return Area(name, children, strategy, appliance)
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise ValueError("Input is not a valid area description (%s)" % str(error))


def area_from_string(string):
    """Recover area from its json string representation"""
    return area_from_dict(json.loads(string))
