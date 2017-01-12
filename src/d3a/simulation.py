from importlib import import_module
from logging import getLogger

import time

from pendulum import Pendulum
from pendulum.interval import Interval
from pendulum.period import Period

from d3a.exceptions import SimulationException
from d3a.models.config import SimulationConfig
# noinspection PyUnresolvedReferences
from d3a import setup as d3a_setup  # noqa
from d3a.util import NonBlockingConsole


log = getLogger(__name__)


class Simulation:
    def __init__(self, setup_module_name: str, simulation_config: SimulationConfig,
                 slowdown: int = 0, paused: bool = False):
        self.paused = paused
        self.simulation_config = simulation_config
        self.slowdown = slowdown
        try:
            setup_module = import_module(".{}".format(setup_module_name), 'd3a.setup')
            log.info("Using setup module '%s'", setup_module_name)
        except ImportError as ex:
            raise SimulationException(
                "Invalid setup module '{}'".format(setup_module_name)) from ex
        self.area = setup_module.get_setup(simulation_config)
        log.info("Starting simulation with config %s", simulation_config)
        self.area.activate()

    def run(self) -> (Period, Interval):
        config = self.simulation_config
        tick_lengths_s = self.simulation_config.tick_length.total_seconds()
        run_start = Pendulum.now()
        paused_time = 0
        slot_count = int(config.duration / config.slot_length) + 1
        with NonBlockingConsole() as console:
            for slot_no in range(config.duration // config.slot_length):
                log.error(
                    "Slot %d of %d (%2.0f%%)",
                    slot_no + 1,
                    slot_count,
                    (slot_no + 1) / slot_count * 100
                )

                for tick_no in range(config.ticks_per_slot):
                    self.handle_input(console)
                    paused_time += self.handle_paused(console)
                    tick_start = time.monotonic()
                    log.debug(
                        "Tick %d of %d in slot %d (%2.0f%%)",
                        tick_no + 1,
                        config.ticks_per_slot,
                        slot_no + 1,
                        (tick_no + 1) / config.ticks_per_slot * 100,
                    )
                    self.area.tick()
                    tick_length = time.monotonic() - tick_start
                    if self.slowdown and tick_length < tick_lengths_s:
                        # Simulation runs faster than real time but a slowdown was requested.
                        tick_diff = tick_lengths_s - tick_length
                        diff_slowdown = tick_diff / 100 * self.slowdown
                        log.debug("Slowdown: %.4f", diff_slowdown)
                        self.handle_input(console, diff_slowdown)
        return Pendulum.now() - run_start, Interval(seconds=paused_time)

    def handle_input(self, console, sleep: float = 0):
        timeout = 0
        start = 0
        if sleep > 0:
            timeout = sleep / 100
            start = time.monotonic()
        while True:
            cmd = console.get_char(timeout)
            if cmd == 'p':
                self.paused = not self.paused
                break
            elif cmd == '+':
                if self.slowdown <= 95:
                    self.slowdown += 5
                    log.critical("Simulation slowdown changed to %d", self.slowdown)
            elif cmd == '-':
                if self.slowdown >= 5:
                    self.slowdown -= 5
                    log.critical("Simulation slowdown changed to %d", self.slowdown)
            if sleep == 0 or time.monotonic() - start >= sleep:
                break

    def handle_paused(self, console):
        if self.paused:
            start = time.monotonic()
            log.critical("Simulation paused. Press 'p' to resume or resume from API.")
            while self.paused:
                self.handle_input(console, 0.1)
            log.critical("Simulation resumed")
            return time.monotonic() - start
        return 0
