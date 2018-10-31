import logging
from logging import getLogger

import click
import dill
from click.types import Choice, File
from click_default_group import DefaultGroup
from colorlog.colorlog import ColoredFormatter


from d3a.exceptions import D3AException
from d3a.models.config import SimulationConfig
from d3a.models.strategy.const import ConstSettings
from d3a.simulation import Simulation
from d3a.util import IntervalType, available_simulation_scenarios
from d3a.web import start_web
from d3a.util import read_settings_from_file
from d3a.util import update_advanced_settings

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


_setup_modules = available_simulation_scenarios


@main.command()
@click.option('-d', '--duration', type=IntervalType('D:H'), default="1d", show_default=True,
              help="Duration of simulation")
@click.option('-t', '--tick-length', type=IntervalType('M:S'), default="1s", show_default=True,
              help="Length of a tick")
@click.option('-s', '--slot-length', type=IntervalType('M:S'), default="15m", show_default=True,
              help="Length of a market slot")
@click.option('-c', '--cloud_coverage', type=int,
              default=ConstSettings.PVSettings.DEFAULT_POWER_PROFILE, show_default=True,
              help="Cloud coverage, 0 for sunny, 1 for partial coverage, 2 for clouds.")
@click.option('-r', '--market_maker_rate', type=str,
              default=str(ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE),
              show_default=True, help="Market maker rate")
@click.option('-f', '--iaa_fee', type=int,
              default=ConstSettings.IAASettings.FEE_PERCENTAGE, show_default=True,
              help="Inter-Area-Agent Fee in percentage")
@click.option('-m', '--market-count', type=int, default=1, show_default=True,
              help="Number of tradable market slots into the future")
@click.option('-i', '--interface', default="0.0.0.0", show_default=True,
              help="REST-API server listening interface")
@click.option('-p', '--port', type=int, default=5000, show_default=True,
              help="REST-API server listening port")
@click.option('--setup', 'setup_module_name', default="default_2a",
              help="Simulation setup module use. Available modules: [{}]".format(
                  ', '.join(_setup_modules)))
@click.option('-g', '--settings_file', default=None,
              help="Settings file path")
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
@click.option('--exit-on-finish', is_flag=True)
@click.option('--exit-on-finish-wait', type=IntervalType('M:S'), default="0",
              help="Wait time before exiting after finishing the simulation run. "
                   "[default: disabled]")
@click.option('--export/--no-export', default=False, help="Export Simulation data in a CSV File")
@click.option('--export-path',  type=str, default=None, show_default=False,
              help="Specify a path for the csv export files (default: ~/d3a-simulation)")
@click.option('--enable-bc', is_flag=True, default=False, help="Run simulation on Blockchain")
@click.option('--enable_bm', is_flag=True, default=False, help="Run simulation on BalancingMarket")
def run(interface, port, setup_module_name, settings_file, slowdown, seed, paused, pause_after,
        repl, export, export_path, reset_on_finish, reset_on_finish_wait, exit_on_finish,
        exit_on_finish_wait, enable_bc, enable_bm, **config_params):
    try:
        if settings_file is not None:
            simulation_settings, advanced_settings = read_settings_from_file(settings_file)
            update_advanced_settings(advanced_settings)
            simulation_config = SimulationConfig(**simulation_settings)
        else:
            simulation_config = SimulationConfig(**config_params)

        api_url = "http://{}:{}/api".format(interface, port)
        ConstSettings.BalancingSettings.ENABLE_BALANCING_MARKET = enable_bm
        simulation = Simulation(
            setup_module_name=setup_module_name,
            simulation_config=simulation_config,
            slowdown=slowdown,
            seed=seed,
            paused=paused,
            pause_after=pause_after,
            use_repl=repl,
            export=export,
            export_path=export_path,
            reset_on_finish=reset_on_finish,
            reset_on_finish_wait=reset_on_finish_wait,
            exit_on_finish=exit_on_finish,
            exit_on_finish_wait=exit_on_finish_wait,
            api_url=api_url,
            redis_job_id=None,
            use_bc=enable_bc
        )
    except D3AException as ex:
        raise click.BadOptionUsage(ex.args[0])
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
