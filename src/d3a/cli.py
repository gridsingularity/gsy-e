import logging
from logging import getLogger
import time

import click
from click.types import Choice
from click_default_group import DefaultGroup
from colorlog.colorlog import ColoredFormatter
from pendulum.pendulum import Pendulum
from ptpython.repl import embed
from d3a.exceptions import D3AException
from d3a.models.appliance.simple import SimpleAppliance
from d3a.models.area import Area
from d3a.models.config import SimulationConfig
from d3a.models.strategy.simple import BuyStrategy, OfferStrategy
from d3a.util import IntervalType
from d3a.web import start_web


log = getLogger(__name__)


@click.group(name='d3a', cls=DefaultGroup, default='run', default_if_no_args=True,
             context_settings={'max_content_width': 120})
@click.option('-l', '--log-level', type=Choice(list(logging._nameToLevel.keys())), default='DEBUG',
              show_default=True, help="Log level")
def main(log_level):
    handler = logging.StreamHandler()
    handler.setFormatter(
        ColoredFormatter(
            "%(log_color)s%(asctime)s.%(msecs)03d %(levelname)-7s (%(lineno)4d) %(name)-25s: "
            "%(message)s%(reset)s",
            datefmt="%H:%M:%S"
        )
    )
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(handler)


@main.command()
@click.option('-d', '--duration', type=IntervalType('H:M'), default="24h", show_default=True,
              help="Duration of simulation")
@click.option('-t', '--tick-length', type=IntervalType('M:S'), default="1s", show_default=True,
              help="Length of a tick")
@click.option('-s', '--slot-length', type=IntervalType('M:S'), default="15m", show_default=True,
              help="Length of a market slot")
@click.option('-m', '--market-count', type=int, default=4, show_default=True,
              help="Number of tradable market slots into the future")
@click.option('-i', '--interface', default="localhost", show_default=True,
              help="REST-API server listening interface")
@click.option('-p', '--port', type=int, default=5000, show_default=True,
              help="REST-API server listening port")
@click.option('--slowdown', type=int, default=0,
              help="Slowdown factor [0 - 100]. "
                   "Where 0 means: no slowdown, ticks are simulated as fast as possible; "
                   "and 100: ticks are simulated in realtime")
@click.option('--repl/--no-repl', default=True, show_default=True,
              help="Start REPL after simulation run.")
def run(interface, port, slowdown, repl, **config_params):
    try:
        config = SimulationConfig(**config_params)
    except D3AException as ex:
        raise click.BadOptionUsage(ex.args[0])
    area = Area(
        'Grid',
        [
            Area(
                'House 1',
                [
                    Area('H1 PV', strategy=PVStrategy(), appliance=SimpleAppliance()),
                    Area('H1 Fridge', strategy=BuyStrategy(buy_chance=.3), appliance=SimpleAppliance())
                ]
            ),
            Area(
                'House 2',
                [
                    Area('H2 PV', strategy=PVStrategy()),
                    Area('H2 Fridge', strategy=BuyStrategy(buy_chance=.4), appliance=SimpleAppliance())
                ]
            ),
            Area('Hydro', strategy=OfferStrategy(offer_chance=.1, price_fraction_choice=(3, 4)))
        ],
        config=config
    )
    log.info("Starting simulation with config %s", config)
    area.activate()

    start_web(interface, port, area)

    tick_lengths_s = config.tick_length.total_seconds()
    run_start = Pendulum.now()
    for slot_no in range(config.duration // config.slot_length):
        for tick_no in range(config.ticks_per_slot):
            tick_start = time.monotonic()
            tick_no_total = (slot_no * config.ticks_per_slot) + tick_no
            log.debug(
                "Slot %d, tick %d of %d (%2.0f%%) / %d of %d (%2.0f%%) total",
                slot_no + 1,
                tick_no + 1,
                config.ticks_per_slot,
                (tick_no + 1) / config.ticks_per_slot * 100,
                tick_no_total + 1,
                config.total_ticks,
                (tick_no_total + 1) / config.total_ticks * 100
            )
            area.tick()
            tick_length = time.monotonic() - tick_start
            if slowdown and tick_length < tick_lengths_s:
                # Simulation runs faster than real time but a slowdown was requested.
                tick_diff = tick_lengths_s - tick_length
                diff_slowdown = tick_diff / 100 * slowdown
                log.debug("Slowdown: %.4f", diff_slowdown)
                time.sleep(diff_slowdown)

    for time_stamp, m in area.markets.items():
        print()
        print(time_stamp)
        print(m.display())
    run_length = Pendulum.now() - run_start
    log.info("Run finished in %s / %.2fx real time.", run_length,
             config.duration / run_length.as_interval())
    log.info("REST-API still running at http://%s:%d/api", interface, port)
    if repl:
        log.info(
            "An interactive REPL has been started. The root Area is available as `root_area`.")
        log.info("Ctrl-D to quit.")
        embed({'root_area': area})
    else:
        log.info("Ctrl-C to quit")
        try:
            while True:
                time.sleep(.5)
        except KeyboardInterrupt:
            print("Exiting")
