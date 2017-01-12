from logging import getLogger
from d3a.models.area import Area
from d3a.models.appliance.appliance import Appliance, ApplianceMode
from d3a.models.appliance.run_algo import RunSchedule
from d3a.models.strategy.const import MAX_FRIDGE_TEMP, MIN_FRIDGE_TEMP
import math

log = getLogger(__name__)


class FridgeAppliance(Appliance):

    def __init__(self, name: str = "Fridge", report_freq: int = 1):
        super().__init__(name, report_freq)
        # Take temp from const.py
        self.max_temp = MAX_FRIDGE_TEMP         # Max temp the fridge can have
        self.min_temp = MIN_FRIDGE_TEMP         # Min temp to avoid frosting
        # Average temp between low and high
        self.current_temp = int((self.max_temp + self.min_temp)/2)
        # TODO have these defined in strategy.const
        # Temperature in fahrenheit, rise every tick fridge is not cooling
        self.heating_per_tick = 0.01
        # Temp drop every tick while the fridge is cooling.
        self.cooling_per_tick = -.1
        # Temp change every tick while the door remains open
        self.temp_change_on_door_open = 5.0
        # Optimize for these many markets/contracts in future
        self.optimize_duration = 1
        # Ticks fridge doors will remain open
        self.door_open_duration = 0
        # Ticks for which fridge will have to cool no matter what
        self.force_cool_ticks = 0

    def handle_door_open(self, duration: int = 1):
        """
        :param duration: number of ticks door will be open for
        Do the following when fridge door is open
        1. Increase fridge temp
        2. If temp increases more than max allowed temp,
            2.a start cooling immediately
            2.b continue cooling until temp drops below max temp
            2.c Optimize running for remaining time in current market cycle.
        3. Else continue to run optimized schedule
        """
        log.warning("Fridge door was opened")
        self.door_open_duration = duration
        # self.current_temp += self.temp_change_on_door_open

    def event_tick(self, *, area: Area):
        if self.door_open_duration > 0:
            log.warning("Fridge door is still open")
            self.door_open_duration -= 1
            self.current_temp += self.temp_change_on_door_open

        if self.current_temp > self.max_temp:    # Fridge is hot, start cooling immediately
            log.warning("Fridge is warm [{} C], start cooling immediately".
                        format(self.current_temp))
            self.update_force_cool_ticks()
            if self.mode == ApplianceMode.OFF:
                self.change_mode_of_operation(ApplianceMode.ON)
            else:
                self.update_iterator(self.energyCurve.get_mode_curve(ApplianceMode.ON))
        elif self.current_temp < self.min_temp:                     # Fridge is too cold
            log.warning("Fridge is too cold [{} C], stop cooling if cooling in progress".
                        format(self.current_temp))
            if self.mode == ApplianceMode.ON:
                self.change_mode_of_operation(ApplianceMode.OFF)
        else:                                    # Fridge is in acceptable temp range
            log.info("Fridge is in acceptable temp range: {} C".format(self.current_temp))
            if self.get_energy_balance() > 0:
                if self.mode == ApplianceMode.OFF:
                    self.change_mode_of_operation(ApplianceMode.ON)
                    self.update_iterator(self.gen_run_schedule())
                elif self.get_tick_count() == 0:
                    self.update_iterator(self.gen_run_schedule())
            else:
                log.info("No trade is available, fridge will try not to use power")

        # Fridge is being force cooled
        if self.force_cool_ticks > 0:
            log.warning("Fridge is being force cooled, ticks remaining: {}".
                        format(self.force_cool_ticks))
            self.force_cool_ticks -= 1
            if self.force_cool_ticks <= 0:
                # This is last force cool tick, optimize remaining ticks
                self.update_iterator(self.gen_run_schedule())
                log.warning("Force cooling has ended {} C".format(self.current_temp))

        if self.is_appliance_consuming_energy():
            self.current_temp += self.cooling_per_tick
            # log.info("Fridge cooling cycle is running: {} C".format(self.current_temp))
        else:
            self.current_temp += self.heating_per_tick
            # log.info("Fridge cooling cycle is not running: {} C".format(self.current_temp))

        self.last_reported_tick += 1

        if self.last_reported_tick == self.report_frequency:
            # report power generation/consumption to area
            self.last_reported_tick = 0
            super().event_tick(area=area)

        # Update strategy with current fridge temp
        if area:
            area.strategy.post(temperature=self.current_temp)

    def update_force_cool_ticks(self):
        """
        Temp of fridge is high, update the number of ticks it will take to bring
        down the temp of fridge just below allowed max temp.
        :param self:
        :return:
        """
        diff = self.current_temp - self.max_temp
        if diff <= 0:
            self.force_cool_ticks = 0
        else:
            ticks_per_cycle = len(self.energyCurve.get_mode_curve(ApplianceMode.ON))
            temp_drop_per_cycle = self.cooling_per_tick * ticks_per_cycle * -1
            cycles_to_run = math.ceil(diff/temp_drop_per_cycle)
            self.force_cool_ticks = cycles_to_run * ticks_per_cycle

        log.warning("It will take fridge {} ticks to cool.".format(self.force_cool_ticks))

    def get_run_skip_cycle_counts(self, ticks_remaining: int):
        """
        Method to generate required and skip-able cycle counts within given remaining ticks.
        :param ticks_remaining: Number of ticks remaining before market cycles
        :return: tuple containing count of required cycles and skip-able cycles
        """
        mid = math.floor((self.max_temp + self.min_temp)/2)
        diff = self.current_temp - mid
        cycles_required = 0
        cycles_skipped = 0
        ticks_per_cycle = len(self.energyCurve.get_mode_curve(ApplianceMode.ON))

        # log.info("Ticks per cycle: {}, temp diff: {}".format(ticks_per_cycle, diff))

        if diff < 0:
            """
            Current temp is lower than mid temp, bring temp up to mid temp
            calculate ticks remaining to optimize run cycles
            """

            t_h_mid = math.ceil((diff * -1)/self.heating_per_tick)
            ticks_remaining -= t_h_mid

        else:
            """
            current temp is above mid temp, bring temp to mid temp
            calculate cycles required to bring temp down to mid.
            calculate ticks required to run these cycles
            calculate ticks remaining
            """
            t_c_mid = math.ceil(diff/(self.cooling_per_tick * -1))
            ticks_remaining -= t_c_mid
            cycles_required += math.ceil(t_c_mid/ticks_per_cycle)

        """
        In remaining ticks, the temp can be allowed to rise to max before cooling is needed
        cycles needed to cool from max to mid are required # of cycles
        cycles needed to cool from mid to min are cycles that can be skipped.
        total cycles = required cycles + cycles that can be skipped
        """
        # ticks to heat to max temp
        t_h_max = math.floor((self.max_temp - mid)/self.heating_per_tick)
        # log.info("Ticks needed to heat to max allowed temp: {}".format(t_h_max))

        # ticks required to cool from max to mid
        t_c_mid = math.ceil((self.max_temp - mid)/(self.cooling_per_tick * -1))
        # log.info("Ticks needed to cool from max to mid: {}".format(t_c_mid))

        # ticks need to rise to max and cool back to mid
        t_range = t_h_max + t_c_mid

        # num of times fridge can swing between mid and max
        quo = ticks_remaining // t_range

        # remainder ticks to account for, shouldn't be more than 1 cycle
        rem = ticks_remaining % t_range

        # log.info("Fridge can swing: {} times in range, extra ticks: {}".format(quo, rem))

        cycles_required += math.ceil((quo * t_c_mid)/ticks_per_cycle)

        # number of ticks cooling is absolutely needed from remaining extra ticks
        t_cooling_req = rem - t_h_max
        # log.info("Cooling required in extra ticks: {}".format(t_cooling_req))

        if t_cooling_req <= 0:   # temp will not rise beyond max in remaining time.
            # use remaining time for cooling, but not required
            cycles_skipped += math.floor(rem/ticks_per_cycle)
        else:       # temp will rise above max, at least 1 cooling will be required
            extra_cooling_cycles = math.ceil(t_cooling_req/ticks_per_cycle)
            cycles_required += 1
            if extra_cooling_cycles > 1:
                cycles_skipped += extra_cooling_cycles - 1

        log.info("Required cycles: {}, skip able cycles: {}".
                 format(cycles_required, cycles_skipped))

        return cycles_required, cycles_skipped

    def gen_run_schedule(self):
        log.info("Generating new run schedule")
        ticks_remaining = \
            self.area.config.ticks_per_slot * (self.optimize_duration - self.get_tick_count())
        cycles = self.get_run_skip_cycle_counts(ticks_remaining)
        cycles_to_run = cycles[0]
        skip_cycles = cycles[1]
        schedule = None
        bids = [self.get_energy_balance()]

        if bids:
            run_schedule = RunSchedule(bids, self.energyCurve.get_mode_curve(ApplianceMode.ON),
                                       self.area.config.ticks_per_slot, cycles_to_run,
                                       skip_cycles, self.get_tick_count())
            schedule = run_schedule.get_run_schedule()

        # log.info("Length of schedule: {}".format(len(schedule)))

        return schedule

    def event_market_cycle(self):
        super().event_market_cycle()
        self.change_mode_of_operation(ApplianceMode.ON)
        self.update_iterator(self.gen_run_schedule())
