import os
import select
import sys
import termios
import tty
from logging import LoggerAdapter

from click.types import ParamType
from pendulum.interval import Interval
from rex import rex

from d3a import get_project_root


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
        elif type == 'M:S':
            self.re = INTERVAL_MS_RE
            self.allowed_formats = "'XXm', 'XXs', 'XXmYYs', 'XX:YY'"
        else:
            raise ValueError("Invalid type. Choices: 'H:M', 'M:S'")

    def convert(self, value, param, ctx):
        match = self.re(value)
        if match:
            return Interval(**{
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
        print('Reading {}'.format(contract_file.name))

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
    return "IAA {}".format(owner.name)


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


def get_contract_source(contract_name):
    contract_path = get_contract_path(contract_name)
    if contract_path not in _CONTRACT_CACHE:
        _CONTRACT_CACHE[contract_path] = ContractJoiner().join(contract_path)
    return _CONTRACT_CACHE[contract_path]
