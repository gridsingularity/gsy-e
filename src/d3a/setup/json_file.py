import os
from d3a.area_serializer import area_from_string


def get_setup(config):
    try:
        setup_path = os.environ['D3A_SETUP_PATH']
        with open(setup_path, 'r') as area_file:
            area_str = area_file.read().replace('\n', '')
        recovered_area = area_from_string(area_str)
        recovered_area.config = config
        return recovered_area
    except KeyError as d3a_key_error:
        raise RuntimeError('D3_SETUP_PATH environment variable not found.') from d3a_key_error
    except FileNotFoundError as d3a_file_error:
        raise RuntimeError('D3A setup file containing area not found on the D3_SETUP_PATH') \
            from d3a_file_error


if __name__ == "__main__":
    get_setup(None)
