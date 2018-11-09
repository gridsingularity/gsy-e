from d3a.d3a_core.area_serializer import area_from_dict


def get_setup(config):
    try:
        area_description = config.area
        return area_from_dict(area_description, config)
    except AttributeError as ex:
        raise RuntimeError('Area not found') from ex
