"""
Copyright 2018 Grid Singularity
This file is part of Grid Singularity Exchange.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
import inspect
import json
import logging
import os
import select
import sys
import termios
import tty
from functools import wraps
from logging import LoggerAdapter, getLogger, getLoggerClass, addLevelName, setLoggerClass, NOTSET
from typing import TYPE_CHECKING

from click.types import ParamType
from gsy_framework.constants_limits import ConstSettings, GlobalConfig, RangeLimit
from gsy_framework.enums import BidOfferMatchAlgoEnum
from gsy_framework.exceptions import GSyException
from gsy_framework.utils import (
    area_name_from_area_or_ma_name, iterate_over_all_modules, str_to_pendulum_datetime,
    get_from_profile_same_weekday_and_time)
from pendulum import duration, from_format, instance, DateTime
from rex import rex

import gsy_e
import gsy_e.constants
from gsy_e import setup as d3a_setup

if TYPE_CHECKING:
    from gsy_e.models.market import MarketBase


gsye_root_path = os.path.dirname(inspect.getsourcefile(gsy_e))


INTERVAL_DH_RE = rex("/^(?:(?P<days>[0-9]{1,4})[d:])?(?:(?P<hours>[0-9]{1,2})[h:])?$/")
INTERVAL_HM_RE = rex("/^(?:(?P<hours>[0-9]{1,4})[h:])?(?:(?P<minutes>[0-9]{1,2})m?)?$/")
INTERVAL_MS_RE = rex("/^(?:(?P<minutes>[0-9]{1,4})[m:])?(?:(?P<seconds>[0-9]{1,2})s?)?$/")
IMPORT_RE = rex("/^import +[\"'](?P<contract>[^\"']+.sol)[\"'];$/")

TRACE = 5


class TraceLogger(getLoggerClass()):
    """TraceLogger"""
    def __init__(self, name, level=NOTSET):
        super().__init__(name, level)

        addLevelName(TRACE, "TRACE")

    def trace(self, msg, *args, **kwargs):
        """
        Log 'msg % args' with severity 'TRACE'.

        To pass exception information, use the keyword argument exc_info with
        a true value, e.g.

        logger.trace("Houston, we have a %s", "thorny problem", exc_info=1)
        """
        if self.isEnabledFor(TRACE):
            self._log(TRACE, msg, args, **kwargs)


setLoggerClass(TraceLogger)

log = getLogger(__name__)


class TaggedLogWrapper(LoggerAdapter):
    """TaggedLogWrapper"""

    def process(self, msg, kwargs):
        msg = f"[{self.extra}] {msg}"
        return msg, kwargs

    def trace(self, msg, *args, **kwargs):
        """
        Delegate a trace call to the underlying logger.
        """
        self.log(TRACE, msg, *args, **kwargs)


class DateType(ParamType):
    """DateType"""
    name = "date"

    def __init__(self, date_type: gsy_e.constants.DATE_FORMAT):
        if date_type == gsy_e.constants.DATE_FORMAT:
            self.allowed_formats = gsy_e.constants.DATE_FORMAT
        else:
            raise ValueError(f"Invalid date_type. Choices: {gsy_e.constants.DATE_FORMAT} ")

    def convert(self, value, param, ctx):
        try:
            converted_format = from_format(value, gsy_e.constants.DATE_FORMAT)
        except ValueError:
            self.fail(
                f"'{value}' is not a valid date. Allowed formats: {self.allowed_formats}")
        return converted_format


class IntervalType(ParamType):
    """IntervalType"""
    name = "interval"

    def __init__(self, interval_type):
        if interval_type == "H:M":
            self.re = INTERVAL_HM_RE
            self.allowed_formats = "'XXh', 'XXm', 'XXhYYm', 'XX:YY'"
        elif interval_type == "D:H":
            self.re = INTERVAL_DH_RE
            self.allowed_formats = "'XXh', 'XXd', 'XXdYYh'"
        elif interval_type == "M:S":
            self.re = INTERVAL_MS_RE
            self.allowed_formats = "'XXm', 'XXs', 'XXmYYs', 'XX:YY'"
        else:
            raise ValueError("Invalid date_type. Choices: 'H:M', 'M:S', 'D:H'")

    def convert(self, value, param, ctx):
        converted_duration = None
        match = self.re(value)
        if match:
            try:
                converted_duration = duration(**{
                    k: int(v) if v else 0
                    for k, v in match.items()
                    if isinstance(k, str)
                })
            except ValueError:
                self.fail(
                    f"'{value}' is not a valid duration. Allowed formats: {self.allowed_formats}")
        return converted_duration


# pylint: disable=attribute-defined-outside-init
class NonBlockingConsole:
    """NonBlockingConsole"""
    def __enter__(self):
        if os.isatty(sys.stdin.fileno()):
            self.old_settings = termios.tcgetattr(sys.stdin)
            tty.setcbreak(sys.stdin.fileno())
        return self

    def __exit__(self, date_type, value, traceback):
        if os.isatty(sys.stdin.fileno()):
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)

    @classmethod
    def get_char(cls, timeout=0):
        """get char"""
        if select.select([sys.stdin], [], [], timeout) == ([sys.stdin], [], []):
            return sys.stdin.read(1)
        return False


def format_interval(interval, show_day=True):
    """Format interval."""
    if interval.days and show_day:
        template = "{i.days:02d}:{i.hours:02d}:{i.minutes:02d}:{i.remaining_seconds:02d}"
    else:
        template = "{i.hours:02d}:{i.minutes:02d}:{i.remaining_seconds:02d}"
    return template.format(i=interval)


d3a_modules_path = d3a_setup.__path__ \
        if ConstSettings.GeneralSettings.SETUP_FILE_PATH is None \
        else [ConstSettings.GeneralSettings.SETUP_FILE_PATH]
available_simulation_scenarios = iterate_over_all_modules(d3a_modules_path)


def parseboolstring(thestring):
    """Parse bool string."""
    if thestring == "None":
        return None
    if thestring[0].upper() == "T":
        return True
    if thestring[0].upper() == "F":
        return False
    return thestring


def read_settings_from_file(settings_file):
    """
    Reads basic and advanced settings from a settings file (json format).
    """
    if os.path.isfile(settings_file):
        with open(settings_file, "r", encoding="utf-8") as sf:
            settings = json.load(sf)
        advanced_settings = settings["advanced_settings"]

        sim_duration = settings["basic_settings"].get("sim_duration")
        slot_length = settings["basic_settings"].get("slot_length")
        tick_length = settings["basic_settings"].get("tick_length")
        simulation_settings = {
            # pylint: disable=used-before-assignment
            "sim_duration": (IntervalType("H:M")(sim_duration)
                             if sim_duration else GlobalConfig.sim_duration),
            "slot_length": (IntervalType("M:S")(slot_length)
                            if slot_length else GlobalConfig.slot_length),
            "tick_length": (IntervalType("M:S")(tick_length)
                            if tick_length else GlobalConfig.tick_length),
            "cloud_coverage": settings["basic_settings"].get(
                "cloud_coverage", advanced_settings["PVSettings"]["DEFAULT_POWER_PROFILE"]),
            "enable_degrees_of_freedom": settings["basic_settings"].get(
                "enable_degrees_of_freedom", GlobalConfig.enable_degrees_of_freedom)
        }
        return simulation_settings, advanced_settings

    raise FileExistsError("Please provide a valid settings_file path")


def update_advanced_settings(advanced_settings):
    """
    Updates ConstSettings class variables with advanced_settings.
    If variable is not part of ConstSettings, an Exception is raised.
    """

    def update_nested_settings(class_object, class_name, settings_dict):
        for set_var, set_val in settings_dict[class_name].items():
            getattr(class_object, set_var)
            if isinstance(set_val, str):
                setattr(class_object, set_var, parseboolstring(set_val))
            elif isinstance(set_val, dict):
                nested_class = getattr(class_object, set_var)
                update_nested_settings(nested_class, set_var, settings_dict[class_name])
            elif isinstance(set_val, list):
                if isinstance(getattr(class_object, set_var), RangeLimit):
                    setattr(class_object, set_var, RangeLimit(*set_val))
            else:
                setattr(class_object, set_var, set_val)

    for settings_class_name in advanced_settings.keys():
        setting_class = getattr(ConstSettings, settings_class_name)
        update_nested_settings(setting_class, settings_class_name, advanced_settings)


def constsettings_to_dict():
    """Constant settings to dict."""

    def convert_nested_settings(class_object, class_name, settings_dict):
        for key, value in dict(class_object.__dict__).items():
            if key.startswith("__"):
                continue

            if class_name not in settings_dict:
                settings_dict[class_name] = {}

            if inspect.isclass(value):
                convert_nested_settings(value, key, settings_dict[class_name])
            else:
                if class_name in settings_dict.keys():
                    settings_dict[class_name][key] = value
                else:
                    settings_dict[class_name] = {key: value}

    try:
        const_settings = {}
        for settings_class_name, settings_class in dict(ConstSettings.__dict__).items():
            if settings_class_name.startswith("__"):
                continue
            convert_nested_settings(settings_class, settings_class_name, const_settings)
        return const_settings
    except Exception as ex:
        raise SyntaxError("Error when serializing the const settings file. Incorrect "
                          "setting structure.") from ex


def retry_function(max_retries=3):
    """Decorator that retries the execution of the function until it returns without
    raising an exception."""
    def decorator_with_max_retries(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            return recursive_retry(f, 0, max_retries, *args, **kwargs)
        return wrapped
    return decorator_with_max_retries


def recursive_retry(functor, retry_count, max_retries, *args, **kwargs):
    """Recursive function that retries the execution of "functor" function if an exception is
    raised from it."""
    try:
        return functor(*args, **kwargs)
    except (AssertionError, GSyException) as e:
        log.debug("Retrying action %s for the %s time.", functor.__name__, retry_count+1)
        if retry_count >= max_retries:
            raise e
        return recursive_retry(functor, retry_count+1, max_retries, *args, **kwargs)


def change_global_config(**kwargs):
    """Change global config."""
    for arg, value in kwargs.items():
        if hasattr(GlobalConfig, arg):
            setattr(GlobalConfig, arg, value)
        else:
            # continue, if config setting is not member of GlobalConfig, e.g. pv_user_profile
            pass


def round_floats_for_ui(number):
    """Round floats for UI."""
    return round(number, 3)


def add_or_create_key(indict, key, value):
    """Add value or create key."""
    if key in indict:
        indict[key] += value
    else:
        indict[key] = value
    return indict


def subtract_or_create_key(indict, key, value):
    """Subtract value of create key."""
    if key in indict:
        indict[key] -= value
    else:
        indict[key] = 0 - value
    return indict


def append_or_create_key(data_dict, key, obj):
    """Append value or create key."""
    if key in data_dict:
        data_dict[key].append(obj)
    else:
        data_dict[key] = [obj]
    return data_dict


def create_subdict_or_update(indict, key, subdict):
    """Create subdict or update."""
    if key in indict:
        indict[key].update(subdict)
    else:
        indict[key] = subdict
    return indict


def write_default_to_dict(indict, key, default_value):
    """Write default to dict."""
    if key not in indict:
        indict[key] = default_value


def convert_str_to_pause_after_interval(start_time, input_str):
    """Convert string to pause after interval."""
    pause_time = str_to_pendulum_datetime(input_str)
    return pause_time - start_time


def convert_unit_to_mega(unit):
    """Convert unit to mega."""
    return unit * 1e-6


def convert_unit_to_kilo(unit):
    """Connvert unit to kilo."""
    return unit * 1e-3


def convert_kilo_to_mega(unit_k):
    """Convert kilo to mega."""
    return unit_k * 1e-3


def convert_percent_to_ratio(unit_percent):
    """Convert percentage to ratio."""
    return unit_percent / 100


def short_offer_bid_log_str(offer_or_bid):
    """Offer bid log string."""
    return f"({{{offer_or_bid.id!s:.6s}}}: {offer_or_bid.energy} kWh)"


# pylint: disable=unspecified-encoding
def export_default_settings_to_json_file():
    """Export default settings to json file."""
    base_settings = {
            "sim_duration": f"{GlobalConfig.DURATION_D*24}h",
            "slot_length": f"{GlobalConfig.SLOT_LENGTH_M}m",
            "tick_length": f"{GlobalConfig.TICK_LENGTH_S}s",
            "cloud_coverage": GlobalConfig.CLOUD_COVERAGE,
            "start_date": instance(GlobalConfig.start_date).format(gsy_e.constants.DATE_FORMAT),
    }
    all_settings = {"basic_settings": base_settings, "advanced_settings": constsettings_to_dict()}
    settings_filename = os.path.join(gsye_root_path, "setup", "gsy_e_settings.json")
    with open(settings_filename, "w") as settings_file:
        settings_file.write(json.dumps(all_settings, indent=2))


def area_sells_to_child(trade, area_name, child_names):
    """Area sells to child."""
    return (
        area_name_from_area_or_ma_name(trade.seller.name) == area_name
        and area_name_from_area_or_ma_name(trade.buyer.name) in child_names)


def child_buys_from_area(trade, area_name, child_names):
    """Child buys from area."""
    return (
        area_name_from_area_or_ma_name(trade.buyer.name) == area_name
        and area_name_from_area_or_ma_name(trade.seller.name) in child_names)


def if_not_in_list_append(target_list, obj):
    """Append object if not already in list."""
    if obj not in target_list:
        target_list.append(obj)


def get_market_maker_rate_from_config(next_market, default_value=None, time_slot=None):
    """Get market maker rate from config."""
    if next_market is None:
        return default_value
    if isinstance(GlobalConfig.market_maker_rate, dict):
        if time_slot is None:
            try:
                time_slot = next_market.time_slot
            except AttributeError as e:
                logging.exception("time_slot parameter is required for future markets.")
                raise e
        return get_from_profile_same_weekday_and_time(GlobalConfig.market_maker_rate,
                                                      time_slot)
    return GlobalConfig.market_maker_rate


def get_feed_in_tariff_rate_from_config(next_market: "MarketBase", time_slot=None):
    """Get feed in tariff rate from config."""
    if next_market is None:
        return 0.
    if isinstance(GlobalConfig.FEED_IN_TARIFF, dict):
        if time_slot is None:
            time_slot = next_market.time_slot
            assert time_slot, "time_slot parameter is missing to get feed-in tariff"

        return get_from_profile_same_weekday_and_time(GlobalConfig.FEED_IN_TARIFF,
                                                      time_slot) or 0.
    return GlobalConfig.FEED_IN_TARIFF


def convert_area_throughput_kVA_to_kWh(transfer_capacity_kWA, slot_length):
    """Convert area throughput frm kVA to kWh."""
    return transfer_capacity_kWA * slot_length.total_minutes() / 60.0 \
        if transfer_capacity_kWA is not None else 0.


def should_read_profile_from_db(profile_uuid):
    """Boolean return if profile to be read from DB."""
    return profile_uuid is not None and gsy_e.constants.CONNECT_TO_PROFILES_DB


def is_external_matching_enabled():
    """Checks if the bid offer match type is set to external
    Returns True if both are matched
    """
    return (ConstSettings.MASettings.BID_OFFER_MATCH_TYPE ==
            BidOfferMatchAlgoEnum.EXTERNAL.value)


class StrategyProfileConfigurationException(Exception):
    """Exception raised when neither a profile nor a profile_uuid are provided for a strategy."""


def is_time_slot_in_past_markets(time_slot: DateTime, current_time_slot: DateTime):
    """Checks if the time_slot should be in the area.past_markets."""
    if ConstSettings.SettlementMarketSettings.ENABLE_SETTLEMENT_MARKETS:
        return (time_slot < current_time_slot.subtract(
            hours=ConstSettings.SettlementMarketSettings.MAX_AGE_SETTLEMENT_MARKET_HOURS))
    return time_slot < current_time_slot


def memory_usage_percent():
    """Returns the percentage of limit utilization."""
    memory_limit_file = "/sys/fs/cgroup/memory/memory.limit_in_bytes"
    memory_usage_file = "/sys/fs/cgroup/memory/memory.usage_in_bytes"

    try:
        with open(memory_limit_file, "r") as limit:
            mem_limit = limit.read()
    except OSError:
        return 0

    try:
        with open(memory_usage_file, "r") as usage:
            mem_usage = usage.read()
    except OSError:
        return 0

    return round(int(mem_usage) / int(mem_limit) * 100)
