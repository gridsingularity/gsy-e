from typing import List
from logging import getLogger
from d3a.util import TaggedLogWrapper

log = getLogger(__name__)


class GlobalMinCost:
    def __init__(self, bids: List, cycle: List, ticks_per_bid: int, cycles_to_run: int = 1,
                 skip: int = 0):
        self.log = TaggedLogWrapper(log, GlobalMinCost.__name__)
        self.bids = bids
        self.normalized_bids = []
        self.normalized_run_cycle = []
        self.cycle = cycle
        self.cycles_to_run = cycles_to_run
        self.t_p_b = ticks_per_bid
        self.skip = skip

        # Effective number of cycles to run
        self.e_n_r = cycles_to_run

        # sliding window size is total ticks needed to run all cycles
        self.run_window = len(self.cycle) * self.cycles_to_run

        for bid in self.bids:
            for count in range(0, self.t_p_b):
                self.normalized_bids.append(bid)

        self.initialize()

    def initialize(self):
        t_b = len(self.normalized_bids)  # Bid time
        t_r = self.run_window  # time needed to run all run cycles
        t_r_s = self.run_window - len(self.cycle) * self.skip  # Run time after skipping allowed cycles

        if t_r > t_b:
            if t_r_s > t_b:
                self.log.warning("Not enough time remaining to run cycles")
                return

            self.log.warning("Cycles may be skipped")
            self.e_n_r = self.cycles_to_run - self.skip

        for cycle in range(0, self.e_n_r):
            self.normalized_run_cycle.extend(self.cycle)

        self.run_window = len(self.normalized_run_cycle)  # Time required to run effective number of cycles.

    def get_min_cost_pass_one(self):
        cost = []

        for index in range(0, len(self.normalized_bids) - len(self.normalized_run_cycle)):
            cost.append(self.get_running_cost(index))

        min_cost = min(cost)
        self.log.debug("Min cost of running cannot exceed: " + str(min_cost))

        return min_cost

    def get_running_cost(self, index: int):
        cost = 0
        for i in range(0, self.run_window):
            cost += float(self.normalized_bids[i + index]) * float(self.normalized_run_cycle[i])

        return cost



