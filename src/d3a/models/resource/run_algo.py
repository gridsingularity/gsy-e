from typing import List
from logging import getLogger
from d3a.util import TaggedLogWrapper
import queue as q

log = getLogger(__name__)

round_off = 10


class Scheduler:
    def __init__(self, bids: List, cycle: List, ticks_per_bid: int, cycles_to_run: int = 1,
                 skip: int = 0):
        self.log = TaggedLogWrapper(log, RunSchedule.__name__)
        self.bids = bids
        self.normalized_bids = []
        self.cycle = cycle
        self.cycles_to_run = cycles_to_run
        self.skip = skip
        self.cost = []
        self.run_schedule = []
        self.limit = 0.0
        self.limit_set = False

        # Effective number of cycles to run
        self.e_n_r = cycles_to_run

        # sliding window size is total ticks needed to run all cycles
        self.run_window = len(self.cycle)

        for bid in self.bids:
            for count in range(0, ticks_per_bid):
                self.normalized_bids.append(bid)

    def initialize(self):
        t_b = len(self.normalized_bids)                         # Bid time
        self.run_window = len(self.cycle)  # Time required to run a cycle.
        t_r = self.run_window                                   # time needed to run a cycle
        t_r_s = self.run_window - len(self.cycle) * self.skip   # Run time after skipping allowed cycles

        if t_r > t_b:
            if t_r_s > t_b:
                self.log.warning("Not enough time remaining to run cycles")
                return

            self.log.warning("Cycles may be skipped")
            self.e_n_r = self.cycles_to_run - self.skip

        self.gen_cost_of_running()
        self.place_run_cycles()

    def gen_cost_of_running(self):
        costq = q.PriorityQueue()
        for index in range(0, len(self.normalized_bids) - self.run_window):
            price = round(self.get_running_cost(index), round_off)
            costq.put((price, index))

        while not costq.empty():
            self.cost.append(costq.get())

    def get_min_cost(self):
        min_cost = self.cost[0][0]
        self.log.debug("Min cost of running cannot exceed: " + str(min_cost))

        return min_cost

    def get_running_cost(self, index: int):
        cost = 0
        for i in range(0, self.run_window):
            cost += float(self.normalized_bids[i + index]) * float(self.cycle[i])

        return cost

    def iterator(self):
        while True:
            for data in self.cost:
                yield data

    def can_be_run(self, start_tick: int):
        can_be = True
        total_cost = 0
        for schedule in self.run_schedule:
            start = schedule[1]
            end = start + self.run_window
            total_cost += schedule[0]
            if (start <= start_tick <= end) or \
                    (start <= start_tick + self.run_window <= end) or \
                    (self.limit_set and total_cost > self.limit):
                can_be = False
                break

        return can_be

    def place_run_cycles(self):
        count = 0
        current = 0
        end = len(self.cost)
        while count < self.e_n_r:
            if current >= end:
                break
            else:
                start = self.cost[current]
                if self.can_be_run(start[1]):
                    self.run_schedule.append((start[0], start[1]))
                    count += 1

            current += 1

    def get_run_schedule(self):
        for schedule in self.run_schedule:
            self.log.info("Cost: {} start at tick: {}".format(schedule[0], schedule[1]))
        return self.run_schedule


class RunSchedule (Scheduler):

    def __init__(self, bids: List, cycle: List, ticks_per_bid: int, cycles_to_run: int = 1,
                 skip: int = 0):
        super().__init__(bids, cycle, ticks_per_bid, cycles_to_run, skip)
        self.initialize()


class RunScheduleLimit (Scheduler):

    def __init__(self, bids: List, cycle: List, ticks_per_bid: int, limit: float, cycles_to_run: int = 1,
                 skip: int = 0):
        super().__init__(bids, cycle, ticks_per_bid, cycles_to_run, skip)
        self.limit = limit
        self.limit_set = True
        self.initialize()


