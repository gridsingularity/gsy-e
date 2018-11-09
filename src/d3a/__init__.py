import os

from d3a.constants import DEFAULT_PRECISION


def get_project_root():
    return os.path.dirname(__file__)


def limit_float_precision(number):
    return round(number, DEFAULT_PRECISION)
