import os

from d3a.constants import DEFAULT_PRECISION


def get_project_root():
    import d3a
    return os.path.dirname(d3a.__file__)


def limit_float_precision(number):
    return round(number, DEFAULT_PRECISION)
