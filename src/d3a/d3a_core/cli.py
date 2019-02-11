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
import logging
from logging import getLogger

import click
import dill
from click.types import Choice, File
from click_default_group import DefaultGroup
from colorlog.colorlog import ColoredFormatter
from multiprocessing import Process
from pendulum import DateTime, today

from d3a.d3a_core.exceptions import D3AException
from d3a.models.config import SimulationConfig
from d3a.models.const import ConstSettings
from d3a.d3a_core.util import DateType
from d3a.d3a_core.util import IntervalType, available_simulation_scenarios, \
    read_settings_from_file, update_advanced_settings

from d3a.d3a_core.simulation import run_simulation
from d3a.constants import TIME_ZONE, DATE_TIME_FORMAT, DATE_FORMAT

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
@click.option('-c', '--cloud-coverage', type=int,
              default=ConstSettings.PVSettings.DEFAULT_POWER_PROFILE, show_default=True,
              help="Cloud coverage, 0 for sunny, 1 for partial coverage, 2 for clouds.")
@click.option('-f', '--iaa-fee', type=int,
              default=ConstSettings.IAASettings.FEE_PERCENTAGE, show_default=True,
              help="Inter-Area-Agent Fee in percentage")
@click.option('-m', '--market-count', type=int, default=1, show_default=True,
              help="Number of tradable market slots into the future")
@click.option('--setup', 'setup_module_name', default="default_2a",
              help="Simulation setup module use. Available modules: [{}]".format(
                  ', '.join(_setup_modules)))
@click.option('-g', '--settings-file', default=None,
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
@click.option('--no-export', is_flag=True, default=False, help="Skip export of simulation data")
@click.option('--export-path',  type=str, default=None, show_default=False,
              help="Specify a path for the csv export files (default: ~/d3a-simulation)")
@click.option('--enable-bc', is_flag=True, default=False, help="Run simulation on Blockchain")
@click.option('--compare-alt-pricing', is_flag=True, default=False,
              help="Compare alternative pricing schemes")
@click.option('--start-date', type=DateType(DATE_FORMAT),
              default=today(tz=TIME_ZONE).format(DATE_FORMAT), show_default=True,
              help=f"Start date of the Simulation ({DATE_FORMAT})")
def run(setup_module_name, settings_file, slowdown, duration, slot_length, tick_length,
        market_count, cloud_coverage, iaa_fee, compare_alt_pricing, start_date, **kwargs):

    try:
        if settings_file is not None:
            simulation_settings, advanced_settings = read_settings_from_file(settings_file)
            update_advanced_settings(advanced_settings)
            simulation_config = SimulationConfig(**simulation_settings)
        else:
            simulation_config = \
                SimulationConfig(duration, slot_length, tick_length, market_count,
                                 cloud_coverage, iaa_fee, start_date=start_date)

        if compare_alt_pricing is True:
            ConstSettings.IAASettings.AlternativePricing.COMPARE_PRICING_SCHEMES = True
            # we need the seconds in the export dir name
            kwargs["export_subdir"] = DateTime.now(tz=TIME_ZONE).format(f"{DATE_TIME_FORMAT}:ss")
            processes = []
            for pricing_scheme in range(0, 4):
                kwargs["pricing_scheme"] = pricing_scheme
                p = Process(target=run_simulation, args=(setup_module_name, simulation_config,
                                                         slowdown, None, kwargs)
                            )
                p.start()
                processes.append(p)

            for p in processes:
                p.join()

        else:
            run_simulation(setup_module_name, simulation_config, slowdown, None,
                           kwargs)

    except D3AException as ex:
        raise click.BadOptionUsage(ex.args[0])


@main.command()
@click.argument('save-file', type=File(mode='rb'))
def resume(save_file):
    simulation = dill.load(save_file)
    simulation.run(resume=True)
