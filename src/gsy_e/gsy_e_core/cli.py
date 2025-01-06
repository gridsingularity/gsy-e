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

import logging
import multiprocessing
import platform

import click
from click.types import Choice
from click_default_group import DefaultGroup
from colorlog.colorlog import ColoredFormatter
from gsy_framework.constants_limits import ConstSettings, DATE_FORMAT, TIME_FORMAT, TIME_ZONE
from gsy_framework.exceptions import GSyException
from gsy_framework.settings_validators import validate_global_settings
from pendulum import today

from gsy_e.gsy_e_core.simulation import run_simulation
from gsy_e.gsy_e_core.util import (
    DateType,
    IntervalType,
    available_simulation_scenarios,
    convert_str_to_pause_after_interval,
    read_settings_from_file,
    update_advanced_settings,
)
from gsy_e.models.config import SimulationConfig

log = logging.getLogger(__name__)


@click.group(
    name="gsy-e",
    cls=DefaultGroup,
    default="run",
    default_if_no_args=True,
    context_settings={"max_content_width": 120},
)
@click.option(
    "-l",
    "--log-level",
    type=Choice(logging._nameToLevel.keys()),
    default="INFO",
    show_default=True,
    help="Log level",
)
def main(log_level):
    """Entrypoint for command-line interface interaction."""
    handler = logging.StreamHandler()
    handler.setLevel(log_level)
    handler.setFormatter(
        ColoredFormatter(
            "%(log_color)s%(asctime)s.%(msecs)03d %(levelname)-8s (%(lineno)4d) %(name)-30s: "
            "%(message)s%(reset)s",
            datefmt="%H:%M:%S",
        )
    )
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(handler)


_setup_modules = available_simulation_scenarios


@main.command()
@click.option(
    "-d",
    "--duration",
    type=IntervalType("D:H"),
    default="1d",
    show_default=True,
    help="Duration of simulation",
)
@click.option(
    "-t",
    "--tick-length",
    type=IntervalType("M:S"),
    default="1s",
    show_default=True,
    help="Length of a tick",
)
@click.option(
    "-s",
    "--slot-length",
    type=IntervalType("M:S"),
    default="15m",
    show_default=True,
    help="Length of a market slot",
)
@click.option(
    "--slot-length-realtime",
    type=IntervalType("M:S"),
    default="0m",
    show_default=True,
    help="Desired duration of slot in realtime",
)
@click.option(
    "--setup",
    "setup_module_name",
    default="default_2a",
    help=("Simulation setup module use. " f"Available modules: [{', '.join(_setup_modules)}]"),
)
@click.option("-g", "--settings-file", default=None, help="Settings file path")
@click.option("--seed", help="Manually specify random seed")
@click.option(
    "--paused",
    is_flag=True,
    default=False,
    show_default=True,
    help="Start simulation in paused state",
)
@click.option(
    "--pause-at",
    type=str,
    default=None,
    help="Automatically pause at a certain time. "
    f"Accepted Input formats: ({DATE_FORMAT}, "
    f"{TIME_FORMAT}) [default: disabled]",
)
@click.option(
    "--incremental",
    is_flag=True,
    default=False,
    show_default=True,
    help="Pause the simulation at the end of each time slot.",
)
@click.option(
    "--repl/--no-repl", default=False, show_default=True, help="Start REPL after simulation run."
)
@click.option("--no-export", is_flag=True, default=False, help="Skip export of simulation data")
@click.option(
    "--export-path",
    type=str,
    default=None,
    show_default=False,
    help="Specify a path for the csv export files (default: ~/gsy-e-simulation)",
)
@click.option("--enable-bc", is_flag=True, default=False, help="Run simulation on Blockchain")
@click.option(
    "--enable-external-connection",
    is_flag=True,
    default=False,
    help="External Agents interaction to simulation during runtime",
)
@click.option(
    "--start-date",
    type=DateType(DATE_FORMAT),
    default=today(tz=TIME_ZONE).format(DATE_FORMAT),
    show_default=True,
    help=f"Start date of the Simulation ({DATE_FORMAT})",
)
@click.option(
    "--enable-dof/--disable-dof",
    is_flag=True,
    default=True,
    help=(
        "Enable or disable Degrees of Freedom " "(orders can't contain attributes/requirements)."
    ),
)
@click.option(
    "-m",
    "--market-type",
    type=int,
    default=ConstSettings.MASettings.MARKET_TYPE,
    show_default=True,
    help="Market type. 1 for one-sided market, 2 for two-sided market, "
    "3 for coefficient-based trading.",
)
@click.option(
    "--country-code",
    type=str,
    default=False,
    help="Country code according to ISO 3166-1 alpha-2.",
)
def run(
    setup_module_name,
    settings_file,
    duration,
    slot_length,
    tick_length,
    enable_external_connection,
    start_date,
    pause_at,
    incremental,
    slot_length_realtime,
    enable_dof: bool,
    market_type: int,
    **kwargs,
):
    """Configure settings and run a simulation."""
    # Force the multiprocessing start method to be 'fork' on macOS.
    if platform.system() == "Darwin":
        multiprocessing.set_start_method("fork")

    try:
        if settings_file is not None:
            simulation_settings, advanced_settings = read_settings_from_file(settings_file)
            update_advanced_settings(advanced_settings)
            validate_global_settings(simulation_settings)
            simulation_settings["external_connection_enabled"] = False
            simulation_config = SimulationConfig(**simulation_settings)
        else:
            assert 1 <= market_type <= 3, "Market type should be an integer between 1 and 3."
            ConstSettings.MASettings.MARKET_TYPE = market_type
            global_settings = {
                "sim_duration": duration,
                "slot_length": slot_length,
                "tick_length": tick_length,
                "enable_degrees_of_freedom": enable_dof,
            }

            validate_global_settings(global_settings)
            simulation_config = SimulationConfig(
                duration,
                slot_length,
                tick_length,
                start_date=start_date,
                external_connection_enabled=enable_external_connection,
                enable_degrees_of_freedom=enable_dof,
            )

        if incremental:
            kwargs["incremental"] = incremental

        if pause_at is not None:
            kwargs["pause_after"] = convert_str_to_pause_after_interval(start_date, pause_at)
        run_simulation(
            setup_module_name, simulation_config, None, None, None, slot_length_realtime, kwargs
        )

    except GSyException as ex:
        log.exception(ex)
        raise click.ClickException(ex.args[0])
