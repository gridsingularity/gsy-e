import os

from d3a.constants import DEFAULT_PRECISION

# *IMPORTANT*: Don't manually change the version here. Use the 'bumpversion' utility.
VERSION = "0.3.0"


def get_project_root():
    return os.path.dirname(__file__)


def limit_float_precision(number):
    return round(number, DEFAULT_PRECISION)
