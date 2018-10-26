import os
import time

import d3a


# *IMPORTANT*: Don't manually change the version here. Use the 'bumpversion' utility.
VERSION = "1.0.0a0"

TIME_FORMAT = "%H:%M"
PENDULUM_TIME_FORMAT = "HH:mm"
TIME_ZONE = "UTC"

DEFAULT_PRECISION = 8


def limit_float_precision(number):
    return round(number, DEFAULT_PRECISION)


def get_project_root():
    return os.path.dirname(d3a.__file__)


def wait_until_timeout_blocking(functor, timeout=10):
    print("wait_until_timeout_blocking")
    current_time = 0
    polling_period = 0.01
    while not functor() and current_time < timeout:
        time.sleep(polling_period)
        current_time += polling_period
    return functor()
