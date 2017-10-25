import logging
from logging import getLogger
from pkgutil import iter_modules

import click
import dill
from click.types import Choice, File
from click_default_group import DefaultGroup
from colorlog.colorlog import ColoredFormatter

from d3a import setup as d3a_setup
from d3a.exceptions import D3AException
from d3a.models.config import SimulationConfig
from d3a.simulation import Simulation
from d3a.util import IntervalType
from d3a.web import start_web


log = getLogger(__name__)


@click.group(name='d3a', cls=DefaultGroup, default='run', default_if_no_args=True,
             context_settings={'max_content_width': 120})
@click.option('-l', '--log-level', type=Choice(list(logging._nameToLevel.keys())), default='DEBUG',
              show_default=True, help="Log level")
def main(log_level):
    handler = logging.StreamHandler()
    handler.setLevel(log_level)
    handler.setFormatter(
        ColoredFormatter(
            "%(log_color)s%(asctime)s.%(msecs)03d %(levelname)-8s (%(lineno)4d) %(name)-30s: "
            "%(message)s%(reset)s",
            datefmt="%H:%M:%S"
        )
    )
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(handler)


_setup_modules = [name for _, name, _ in iter_modules(d3a_setup.__path__)]


@main.command()
@click.option('-d', '--duration', type=IntervalType('H:M'), default="24h", show_default=True,
              help="Duration of simulation")
@click.option('-t', '--tick-length', type=IntervalType('M:S'), default="1s", show_default=True,
              help="Length of a tick")
@click.option('-s', '--slot-length', type=IntervalType('M:S'), default="15m", show_default=True,
              help="Length of a market slot")
@click.option('-m', '--market-count', type=int, default=5, show_default=True,
              help="Number of tradable market slots into the future")
@click.option('-i', '--interface', default="0.0.0.0", show_default=True,
              help="REST-API server listening interface")
@click.option('-p', '--port', type=int, default=5000, show_default=True,
              help="REST-API server listening port")
@click.option('--setup', 'setup_module_name', default="default",
              help="Simulation setup module use. Available modules: [{}]".format(
                  ', '.join(_setup_modules)))
@click.option('--slowdown', type=int, default=0,
              help="Slowdown factor [0 - 10,000]. "
                   "Where 0 means: no slowdown, ticks are simulated as fast as possible; "
                   "and 100: ticks are simulated in realtime")
@click.option('--seed', help="Manually specify random seed")
@click.option('--paused', is_flag=True, default=False, show_default=True,
              help="Start simulation in paused state")
@click.option('--pause-after', type=IntervalType('H:M'), default="0",
              help="Automatically pause after a certain time.  [default: disabled]")
@click.option('--repl/--no-repl', default=False, show_default=True,
              help="Start REPL after simulation run.")
@click.option('--reset-on-finish/--no-reset-on-finish', default=False, show_default=True,
              help="Automatically reset simulation after it finishes.")
@click.option('--reset-on-finish-wait', type=IntervalType('M:S'), default="1m", show_default=True,
              help="Wait time before resetting after finishing the simulation run")
@click.option('--export/--no-export', default=False, help="Export Simulation data in a CSV File")
@click.option('--export-path',  type=str, default=None, show_default=False,
              help="Specify a path for the csv export files (default: ~/d3a-simulation)")
def run(interface, port, setup_module_name, slowdown, seed, paused, pause_after, repl,
        export, export_path, reset_on_finish, reset_on_finish_wait, **config_params):
    try:
        simulation_config = SimulationConfig(**config_params)
    except D3AException as ex:
        raise click.BadOptionUsage(ex.args[0])

    api_url = "http://{}:{}/api".format(interface, port)
    simulation = Simulation(
        setup_module_name,
        simulation_config,
        slowdown,
        seed,
        paused,
        pause_after,
        repl,
        export,
        export_path,
        reset_on_finish,
        reset_on_finish_wait,
        api_url
    )
    start_web(interface, port, simulation)
    simulation.run()


@main.command()
@click.option('-i', '--interface', default="0.0.0.0", show_default=True,
              help="REST-API server listening interface")
@click.option('-p', '--port', type=int, default=5000, show_default=True,
              help="REST-API server listening port")
@click.argument('save-file', type=File(mode='rb'))
def resume(save_file, interface, port):
    simulation = dill.load(save_file)
    start_web(interface, port, simulation)
    simulation.run(resume=True)
