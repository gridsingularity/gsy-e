import select
import sys
import termios
import tty
from logging import LoggerAdapter, getLogger
import json

from click.types import ParamType
from pendulum import duration
from rex import rex
from pkgutil import walk_packages
from datetime import timedelta

from d3a import get_project_root
from d3a import setup as d3a_setup
from d3a.models.strategy.const import ConstSettings

import d3a
import inspect
import os
d3a_path = os.path.dirname(inspect.getsourcefile(d3a))

log = getLogger(__name__)


INTERVAL_DH_RE = rex("/^(?:(?P<days>[0-9]{1,4})[d:])?(?:(?P<hours>[0-9]{1,2})[h:])?$/")
INTERVAL_HM_RE = rex("/^(?:(?P<hours>[0-9]{1,4})[h:])?(?:(?P<minutes>[0-9]{1,2})m?)?$/")
INTERVAL_MS_RE = rex("/^(?:(?P<minutes>[0-9]{1,4})[m:])?(?:(?P<seconds>[0-9]{1,2})s?)?$/")
IMPORT_RE = rex("/^import +[\"'](?P<contract>[^\"']+.sol)[\"'];$/")

_CONTRACT_CACHE = {}


class TaggedLogWrapper(LoggerAdapter):
    def process(self, msg, kwargs):
        msg = "[{}] {}".format(self.extra, msg)
        return msg, kwargs


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
            raise ValueError("Invalid type. Choices: 'H:M', 'M:S'")

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
            print('Skipping duplicate {}'.format(contract_file.name))
            return []

        self.seen.add(contract_file.name)
        log.debug('Reading contract file "%s"', contract_file.name)

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


def make_ba_name(owner):
    return f"BA {owner.name}"


def area_name_from_area_or_iaa_name(name):
    return name[4:] if name[:4] == 'IAA ' else name


def format_interval(interval, show_day=True):
    if interval.days and show_day:
        template = "{i.days:02d}:{i.hours:02d}:{i.minutes:02d}:{i.remaining_seconds:02d}"
    else:
        template = "{i.hours:02d}:{i.minutes:02d}:{i.remaining_seconds:02d}"
    return template.format(i=interval)


def simulation_info(simulation):
    current_time = format_interval(
        simulation.area.current_tick * simulation.area.config.tick_length,
        show_day=False
    )
    return {
        'config': simulation.area.config.as_dict(),
        'finished': simulation.finished,
        'aborted': simulation.is_stopped,
        'current_tick': simulation.area.current_tick,
        'current_time': current_time,
        'current_date': simulation.area.now.format('%Y-%m-%d'),
        'paused': simulation.paused,
        'slowdown': simulation.slowdown
    }


def get_contract_path(contract_name):
    if contract_name.endswith(".sol"):
        contract_name = contract_name[:-4]
    contract_path = os.path.join(
        get_project_root(),
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
    for loader, module_name, is_pkg in walk_packages(d3a_setup.__path__):
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
            "duration": IntervalType('H:M')(
                settings["basic_settings"].get('duration', timedelta(hours=24))),
            "slot_length": IntervalType('M:S')(
                settings["basic_settings"].get('slot_length', timedelta(minutes=15))),
            "tick_length": IntervalType('M:S')(
                settings["basic_settings"].get('tick_length', timedelta(seconds=15))),
            "market_count": settings["basic_settings"].get('market_count', 1),
            "cloud_coverage": settings["basic_settings"].get(
                'cloud_coverage', advanced_settings["PVSettings"]["DEFAULT_POWER_PROFILE"]),
            "market_maker_rate": settings["basic_settings"].get(
                'market_maker_rate', advanced_settings["GeneralSettings"]
                ["DEFAULT_MARKET_MAKER_RATE"]),
            "iaa_fee": settings["basic_settings"].get(
                'INTER_AREA_AGENT_FEE_PERCENTAGE',
                advanced_settings["IAASettings"]["FEE_PERCENTAGE"])
        }
        return simulation_settings, advanced_settings
    else:
        raise FileExistsError("Please provide a valid settings_file path")


def update_advanced_settings(advanced_settings):
    """
    Updates ConstSettings class variables with advanced_settings.
    If variable is not part of ConstSettings, an Exception is raised.
    """
    for settings_class_name in advanced_settings.keys():
        setting_class = getattr(ConstSettings, settings_class_name)
        for set_var, set_val in advanced_settings[settings_class_name].items():
            getattr(setting_class, set_var)
            if isinstance(set_val, str):
                setattr(setting_class, set_var, parseboolstring(set_val))
            else:
                setattr(setting_class, set_var, set_val)


def generate_market_slot_list(area):
    """
    Returns a list of all slot times
    """
    market_slots = []
    for slot_time in [
        area.now + (area.config.slot_length * i) for i in range(
            (area.config.duration + (area.config.market_count * area.config.slot_length)) //
            area.config.slot_length)]:
        market_slots.append(slot_time)
    return market_slots


def constsettings_to_dict():
    const_settings = {}
    for settings_class_name, settings_class in dict(ConstSettings.__dict__).items():
        if not settings_class_name.startswith("__"):
            for key, value in dict(settings_class.__dict__).items():
                if not key.startswith("__"):
                    if settings_class_name in const_settings.keys():
                        const_settings[settings_class_name][key] = value
                    else:
                        const_settings[settings_class_name] = {key: value}
    return const_settings
