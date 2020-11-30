"""
Copyright 2018 Grid Singularity
This file is part of D3A.

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
import pendulum
import select
import sys
import termios
import tty
import json
import d3a
import inspect
import os

from collections import OrderedDict
from click.types import ParamType
from pendulum import duration, from_format, datetime
from rex import rex
from pkgutil import walk_packages
from functools import wraps
from logging import LoggerAdapter, getLogger, getLoggerClass, addLevelName, setLoggerClass, NOTSET

import d3a.constants
from d3a import setup as d3a_setup
from d3a_interface.constants_limits import ConstSettings
from d3a_interface.exceptions import D3AException
from d3a.constants import DATE_FORMAT, TIME_ZONE
from d3a_interface.constants_limits import GlobalConfig, RangeLimit
from d3a_interface.utils import generate_market_slot_list_from_config, str_to_pendulum_datetime,\
    format_datetime

d3a_path = os.path.dirname(inspect.getsourcefile(d3a))


INTERVAL_DH_RE = rex("/^(?:(?P<days>[0-9]{1,4})[d:])?(?:(?P<hours>[0-9]{1,2})[h:])?$/")
INTERVAL_HM_RE = rex("/^(?:(?P<hours>[0-9]{1,4})[h:])?(?:(?P<minutes>[0-9]{1,2})m?)?$/")
INTERVAL_MS_RE = rex("/^(?:(?P<minutes>[0-9]{1,4})[m:])?(?:(?P<seconds>[0-9]{1,2})s?)?$/")
IMPORT_RE = rex("/^import +[\"'](?P<contract>[^\"']+.sol)[\"'];$/")

_CONTRACT_CACHE = {}

TRACE = 5


class TraceLogger(getLoggerClass()):
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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def process(self, msg, kwargs):
        msg = "[{}] {}".format(self.extra, msg)
        return msg, kwargs

    def trace(self, msg, *args, **kwargs):
        """
        Delegate a trace call to the underlying logger.
        """
        self.log(TRACE, msg, *args, **kwargs)


class DateType(ParamType):
    name = 'date'

    def __init__(self, type):
        if type == DATE_FORMAT:
            self.allowed_formats = DATE_FORMAT
        else:
            raise ValueError(f"Invalid type. Choices: {DATE_FORMAT} ")

    def convert(self, value, param, ctx):
        try:
            return from_format(value, DATE_FORMAT)
        except ValueError:
            self.fail(
                "'{}' is not a valid date. Allowed formats: {}".format(
                    value,
                    self.allowed_formats
                )
            )


class IntervalType(ParamType):
    name = 'interval'

    def __init__(self, type):
        if type == 'H:M':
            self.re = INTERVAL_HM_RE
            self.allowed_formats = "'XXh', 'XXm', 'XXhYYm', 'XX:YY'"
        elif type == 'D:H':
            self.re = INTERVAL_DH_RE
            self.allowed_formats = "'XXh', 'XXd', 'XXdYYh'"
        elif type == 'M:S':
            self.re = INTERVAL_MS_RE
            self.allowed_formats = "'XXm', 'XXs', 'XXmYYs', 'XX:YY'"
        else:
            raise ValueError("Invalid type. Choices: 'H:M', 'M:S', 'D:H'")

    def convert(self, value, param, ctx):
        match = self.re(value)
        if match:
            return duration(**{
                k: int(v) if v else 0
                for k, v in match.items()
                if isinstance(k, str)
            })
        self.fail(
            "'{}' is not a valid duration. Allowed formats: {}".format(
                value,
                self.allowed_formats
            )
        )


class NonBlockingConsole:
    def __enter__(self):
        if os.isatty(sys.stdin.fileno()):
            self.old_settings = termios.tcgetattr(sys.stdin)
            tty.setcbreak(sys.stdin.fileno())
        return self

    def __exit__(self, type, value, traceback):
        if os.isatty(sys.stdin.fileno()):
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)

    def get_char(self, timeout=0):
        if select.select([sys.stdin], [], [], timeout) == ([sys.stdin], [], []):
            return sys.stdin.read(1)
        return False


class ContractJoiner(object):
    def __init__(self):
        self.have_pragma = None
        self.seen = None

    def join(self, contract_file_path):
        self.have_pragma = False
        self.seen = set()

        old_cwd = os.getcwd()
        try:
            os.chdir(os.path.dirname(contract_file_path))
            with open(contract_file_path) as contract_file:
                return "\n".join(self._join(contract_file))
        finally:
            os.chdir(old_cwd)

    def _join(self, contract_file):

        out = []
        if contract_file.name in self.seen:
            return []

        self.seen.add(contract_file.name)
        log.trace('Reading contract file "%s"', contract_file.name)

        for line in contract_file:
            line = line.strip('\r\n')
            stripped_line = line.strip()
            if stripped_line.startswith('pragma'):
                if not self.have_pragma:
                    self.have_pragma = True
                    out.append(line)
            elif stripped_line.startswith('import'):
                match = IMPORT_RE(stripped_line)
                if match:
                    next_file = match.get('contract')
                    if next_file and os.path.exists(next_file):
                        with open(next_file) as next_contract:
                            out.extend(self._join(next_contract))

            else:
                out.append(line)
        return out


def make_iaa_name(owner):
    return f"IAA {owner.name}"


def make_iaa_name_from_dict(owner):
    return f"IAA {owner['name']}"


def make_ba_name(owner):
    return f"BA {owner.name}"


def area_name_from_area_or_iaa_name(name):
    return name[4:] if name[:4] == 'IAA ' else name


def is_timeslot_in_simulation_duration(config, time_slot):
    return config.start_date <= time_slot < config.end_date or \
           d3a.constants.IS_CANARY_NETWORK


def format_interval(interval, show_day=True):
    if interval.days and show_day:
        template = "{i.days:02d}:{i.hours:02d}:{i.minutes:02d}:{i.remaining_seconds:02d}"
    else:
        template = "{i.hours:02d}:{i.minutes:02d}:{i.remaining_seconds:02d}"
    return template.format(i=interval)


def get_contract_path(contract_name):
    if contract_name.endswith(".sol"):
        contract_name = contract_name[:-4]
    contract_path = os.path.join(
        d3a.get_project_root(),
        'blockchain',
        'contracts',
        "{}.sol".format(contract_name)
    )
    return os.path.realpath(contract_path)


def get_cached_joined_contract_source(contract_name):
    contract_path = get_contract_path(contract_name)
    if contract_path not in _CONTRACT_CACHE:
        _CONTRACT_CACHE[contract_path] = ContractJoiner().join(contract_path)
    return _CONTRACT_CACHE[contract_path]


def iterate_over_all_d3a_setup():
    module_list = []
    d3a_modules_path = d3a_setup.__path__ \
        if ConstSettings.GeneralSettings.SETUP_FILE_PATH is None \
        else [ConstSettings.GeneralSettings.SETUP_FILE_PATH]
    for loader, module_name, is_pkg in walk_packages(d3a_modules_path):
        if is_pkg:
            loader.find_module(module_name).load_module(module_name)
        else:
            module_list.append(module_name)
    return module_list


available_simulation_scenarios = iterate_over_all_d3a_setup()


def parseboolstring(thestring):
    if thestring == "None":
        return None
    elif thestring[0].upper() == 'T':
        return True
    elif thestring[0].upper() == 'F':
        return False
    else:
        return thestring


def read_settings_from_file(settings_file):
    """
    Reads basic and advanced settings from a settings file (json format).
    """
    if os.path.isfile(settings_file):
        with open(settings_file, "r") as sf:
            settings = json.load(sf)
        advanced_settings = settings["advanced_settings"]
        simulation_settings = {
            "sim_duration": IntervalType('H:M')(
                settings["basic_settings"].get('sim_duration', GlobalConfig.sim_duration)),
            "slot_length": IntervalType('M:S')(
                settings["basic_settings"].get('slot_length', GlobalConfig.slot_length)),
            "tick_length": IntervalType('M:S')(
                settings["basic_settings"].get('tick_length', GlobalConfig.tick_length)),
            "market_count": settings["basic_settings"].get('market_count', 1),
            "cloud_coverage": settings["basic_settings"].get(
                'cloud_coverage', advanced_settings["PVSettings"]["DEFAULT_POWER_PROFILE"])
        }
        return simulation_settings, advanced_settings
    else:
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


def generate_market_slot_list(start_date=None, time_span=None):
    if not start_date:
        start_date = GlobalConfig.start_date
    if not time_span:
        time_span = GlobalConfig.sim_duration
    sim_duration_plus_future_markets = time_span + GlobalConfig.slot_length * \
        (GlobalConfig.market_count - 1)
    market_slot_list = \
        generate_market_slot_list_from_config(sim_duration=sim_duration_plus_future_markets,
                                              start_date=start_date,
                                              market_count=GlobalConfig.market_count,
                                              slot_length=GlobalConfig.slot_length)

    if not getattr(GlobalConfig, 'market_slot_list', []):
        GlobalConfig.market_slot_list = market_slot_list
    return market_slot_list


def get_market_slot_time_str(slot_number, config):
    return format_datetime(
        config.start_date.add(
            minutes=config.slot_length.minutes * slot_number
        )
    )


def constsettings_to_dict():

    def convert_nested_settings(class_object, class_name, settings_dict):
        for key, value in dict(class_object.__dict__).items():
            if key.startswith("__"):
                continue
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
    except Exception:
        raise SyntaxError("Error when serializing the const settings file. Incorrect "
                          "setting structure.")


def retry_function(max_retries=3):
    def decorator_with_max_retries(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            return recursive_retry(f, 0, max_retries, *args, **kwargs)
        return wrapped
    return decorator_with_max_retries


def recursive_retry(functor, retry_count, max_retries, *args, **kwargs):
    try:
        return functor(*args, **kwargs)
    except (AssertionError, D3AException) as e:
        log.debug(f"Retrying action {functor.__name__} for the {retry_count+1} time.")
        if retry_count >= max_retries:
            raise e
        return recursive_retry(functor, retry_count+1, max_retries, *args, **kwargs)


def change_global_config(**kwargs):
    for arg, value in kwargs.items():
        if hasattr(GlobalConfig, arg):
            setattr(GlobalConfig, arg, value)
        else:
            # continue, if config setting is not member of GlobalConfig, e.g. pv_user_profile
            pass


def validate_const_settings_for_simulation():
    from d3a_interface.constants_limits import ConstSettings
    # If schemes are not compared and an individual scheme is selected
    # And the market type is not single sided market
    # This is a wrong configuration and an exception is raised
    if not ConstSettings.IAASettings.AlternativePricing.COMPARE_PRICING_SCHEMES and \
       ConstSettings.IAASettings.MARKET_TYPE != 1 and \
       ConstSettings.IAASettings.AlternativePricing.PRICING_SCHEME != 0:
        assert False, "Alternate pricing schemes are only usable with an one sided market."

    # If an alternate price is selected on compare schemes
    # There should be a single sided market
    if ConstSettings.IAASettings.AlternativePricing.COMPARE_PRICING_SCHEMES and \
       ConstSettings.IAASettings.AlternativePricing.PRICING_SCHEME != 0:
        ConstSettings.IAASettings.MARKET_TYPE = 1


def round_floats_for_ui(number):
    return round(number, 3)


def add_or_create_key(dict, key, value):
    if key in dict:
        dict[key] += value
    else:
        dict[key] = value
    return dict


def subtract_or_create_key(dict, key, value):
    if key in dict:
        dict[key] -= value
    else:
        dict[key] = 0 - value
    return dict


def append_or_create_key(dict, key, obj):
    if key in dict:
        dict[key].append(obj)
    else:
        dict[key] = [obj]
    return dict


def create_subdict_or_update(indict, key, subdict):
    if key in indict:
        indict[key].update(subdict)
    else:
        indict[key] = subdict
    return indict


def write_default_to_dict(indict, key, default_value):
    if key not in indict:
        indict[key] = default_value


def convert_str_to_pause_after_interval(start_time, input_str):
    pause_time = str_to_pendulum_datetime(input_str)
    return pause_time - start_time


def convert_unit_to_mega(unit):
    return unit * 1e-6


def convert_unit_to_kilo(unit):
    return unit * 1e-3


def convert_kilo_to_mega(unit_k):
    return unit_k * 1e-3


def convert_percent_to_ratio(unit_percent):
    return unit_percent / 100


def short_offer_bid_log_str(offer_or_bid):
    return f"({{{offer_or_bid.id!s:.6s}}}: {offer_or_bid.energy} kWh)"


def export_default_settings_to_json_file():
    base_settings = {
            "sim_duration": f"{GlobalConfig.DURATION_D*24}h",
            "slot_length": f"{GlobalConfig.SLOT_LENGTH_M}m",
            "tick_length": f"{GlobalConfig.TICK_LENGTH_S}s",
            "market_count": GlobalConfig.MARKET_COUNT,
            "cloud_coverage": GlobalConfig.CLOUD_COVERAGE,
            "start_date": pendulum.instance(GlobalConfig.start_date).format(DATE_FORMAT),
    }
    all_settings = {"basic_settings": base_settings, "advanced_settings": constsettings_to_dict()}
    settings_filename = os.path.join(d3a_path, "setup", "d3a-settings.json")
    with open(settings_filename, "w") as settings_file:
        settings_file.write(json.dumps(all_settings, indent=2))


def area_sells_to_child(trade, area_name, child_names):
    return area_name_from_area_or_iaa_name(trade.seller) == \
            area_name and area_name_from_area_or_iaa_name(trade.buyer) in child_names


def child_buys_from_area(trade, area_name, child_names):
    return area_name_from_area_or_iaa_name(trade.buyer) == \
        area_name and area_name_from_area_or_iaa_name(trade.seller) in child_names


def if_not_in_list_append(target_list, obj):
    if obj not in target_list:
        target_list.append(obj)


def get_current_market_maker_rate(market_slot):
    mmr_rate = GlobalConfig.market_maker_rate
    if isinstance(mmr_rate, dict):
        return mmr_rate[market_slot] if market_slot in mmr_rate else None
    else:
        return mmr_rate


def convert_area_throughput_kVA_to_kWh(transfer_capacity_kWA, slot_length):
    return transfer_capacity_kWA * slot_length.total_minutes() / 60.0 \
        if transfer_capacity_kWA is not None else 0.


def find_object_of_same_weekday_and_time(indict, time_slot, ignore_not_found=False):
    if d3a.constants.IS_CANARY_NETWORK:
        start_time = list(indict.keys())[0]
        add_days = time_slot.weekday() - start_time.weekday()
        if add_days < 0:
            add_days += 7
        timestamp_key = datetime(year=start_time.year, month=start_time.month, day=start_time.day,
                                 hour=time_slot.hour, minute=time_slot.minute, tz=TIME_ZONE).add(
            days=add_days)

        if timestamp_key in indict:
            return indict[timestamp_key]
        else:
            if not ignore_not_found:
                log.error(f"Weekday and time not found in dict for {time_slot}")
            return

    else:
        return indict[time_slot]


def convert_W_to_kWh(power_W, slot_length):
    return (slot_length / duration(hours=1)) * power_W / 1000


def convert_W_to_Wh(power_W, slot_length):
    return (slot_length / duration(hours=1)) * power_W


def convert_kW_to_kWh(power_W, slot_length):
    return convert_W_to_Wh(power_W, slot_length)


def return_ordered_dict(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        return OrderedDict(sorted(function(*args, **kwargs).items()))
    return wrapper


def get_simulation_queue_name():
    listen_to_cn = os.environ.get("LISTEN_TO_CANARY_NETWORK_REDIS_QUEUE", "no") == "yes"
    return "canary_network" if listen_to_cn else "d3a"
