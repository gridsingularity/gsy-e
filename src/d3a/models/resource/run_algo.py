from typing import List
from logging import getLogger
from d3a.util import TaggedLogWrapper
import queue as q

log = getLogger(__name__)

round_off = 10


class ReversePriorityQueue(q.PriorityQueue):
    """
    A wrapper class to obtain reverse priority queue functionality
    """

    def __init__(self):
        super().__init__(0)

    def put(self, item, block=True, timeout=None):
        super().put((item[0] * -1, item[1]))

    def get(self, block=True, timeout=None):
        item = super().get()
        item = ((item[0] * -1), item[1])
        return item


class Scheduler:
    """
    Base class to handle scheduling related optimization.
    """
    def __init__(self, bids: List, cycle: List, ticks_per_bid: int, cycles_to_run: int = 1,
                 skip: int = 0, ticks_elapsed: int = 0, maximize: bool = False):
        """
        :param bids: List containing prices in contract spread across a certain time period.
        :param cycle: List containing power consumption curve sampled for each tick.
        :param ticks_per_bid: number of ticks in a single contract period
        :param cycles_to_run: number of appliance cycles that need to be run.
        :param skip: number of appliance cycles that can be skip
        :param ticks_elapsed number of ticks alaredy elapsed
        :param maximize: run algorith for maximizing run cost
        """
        self.log = TaggedLogWrapper(log, RunSchedule.__name__)
        self.bids = bids
        self.normalized_bids = []
        self.cycle = cycle
        self.cycles_to_run = cycles_to_run
        self.skip = skip
        self.cost = []
        self.optimal_schedule = []
        self.limit = 0.0
        self.limit_set = False
        self.maximize = maximize
        self.run_schedule = []

        # Effective number of cycles to run
        self.e_n_r = cycles_to_run

        # sliding window size is total ticks needed to run all cycles
        self.run_window = len(self.cycle)

        for bid in self.bids:
            for count in range(0, ticks_per_bid):
                self.normalized_bids.append(bid)

        # Truncate elapsed ticks from optimization
        self.normalized_bids = self.normalized_bids[ticks_elapsed:]

    def initialize(self):
        """
        This method initializes member variables with values derived from provided parameters.
        This method also runs the algorithm and keeps the result ready for quick retrieval.
        """
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

        self.run_schedule = [0] * len(self.normalized_bids)

        self.calculate_running_cost()
        self.place_run_cycles()
        self.gen_run_schedule()

    def calculate_running_cost(self):
        """
        This method calculates cost of running appliance, in a sliding window manner.
        saves the result in a cost list, in either ascending or descending order based on maximize flag
        a tuple with cost or running and index (tick count) is put into min heap.
        """
        costq = ReversePriorityQueue() if self.maximize else q.PriorityQueue()
        for index in range(0, len(self.normalized_bids) - self.run_window):
            price = round(self.get_running_cost(index), round_off)
            costq.put((price, index))

        while not costq.empty():
            self.cost.append(costq.get())

    def get_running_cost(self, index: int):
        """
        Method to calculate running cost of appliance starting at a given tick time in bids array
        :param index: tick index in bids array
        """
        cost = 0
        for i in range(0, self.run_window):
            cost += float(self.normalized_bids[i + index]) * float(self.cycle[i])

        return cost

    def iterator(self):
        while True:
            for data in self.cost:
                yield data

    def can_be_run(self, start_tick: int):
        """
        Helper method to find if an appliance can run at a given tick time.
        Appliance cannot run, if the appliance is already scheduled to be running at this tick
        :param start_tick: Tick at which the appliance needs to run at.
        """
        can_be = True
        total_cost = 0
        for schedule in self.optimal_schedule:
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
        """
        Method places all the start ticks and price of running appliance, in a simple list as tuples.
        """
        count = 0
        current = 0
        end = len(self.cost)
        # self.run_schedule = []
        self.log.error("E_N_R: {}, window: {}, cycle_len: {}".format(self.e_n_r, self.run_window, len(self.cycle)))
        while count < self.e_n_r:
            if current >= end:
                break
            else:
                start = self.cost[current]
                if self.can_be_run(start[1]):
                    self.optimal_schedule.append((start[0], start[1]))
                    count += 1
                    # self.run_schedule += self.cycle
                    current += self.run_window - 1
                # else:
                #     self.run_schedule.append(0)
            current += 1

        # self.log.error("current: {}, end: {}, schedule_len: {}".format(current, end, len(self.run_schedule)))
        # if current < end:
        #     for i in range(current, end):
        #         self.run_schedule.append(0)

    def gen_run_schedule(self):
        self.run_schedule = []
        for val in self.optimal_schedule:
            index = val[1]
            for i in range(0, self.run_window):
                self.run_schedule[index + i] = self.cycle[i]

    def get_optimal_schedule(self):
        """
        Method returns a list containing tuples with start tick and cost of running appliance.
        """
        for schedule in self.optimal_schedule:
            self.log.info("Cost: {} start at tick: {}".format(schedule[0], schedule[1]))
        return self.optimal_schedule

    def get_run_schedule(self):
        """
        This method returns the final run schedule with run curves placed at optimal tick times.
        :return: List containing the entire run schedule
        """
        return self.run_schedule


class RunSchedule (Scheduler):
    """
    The concrete class inherits from Schedule class and can be used to generate optimal schedules to run appliances
    in order to minimize running cost during over a/multiple bid contracts.
    if maximize is set to True, the object optimizes for max running cost.
    """
    def __init__(self, bids: List, cycle: List, ticks_per_bid: int, cycles_to_run: int = 1,
                 skip: int = 0, ticks_elapsed=0, maximize: bool = False):
        super().__init__(bids, cycle, ticks_per_bid, cycles_to_run, skip, ticks_elapsed, maximize)
        self.initialize()


class RunScheduleLimit (Scheduler):
    """
    This concrete class inherits from Schedule class and can be used to generate optimal schedules limited by
    an upper cost limit provided by the user. Depending on maximize flag, class can optimize for max cost.
    """
    def __init__(self, bids: List, cycle: List, ticks_per_bid: int, limit: float, cycles_to_run: int = 1,
                 skip: int = 0, ticks_elapsed=0, maximize: bool = False):
        super().__init__(bids, cycle, ticks_per_bid, cycles_to_run, skip, ticks_elapsed, maximize)
        self.limit = limit
        self.limit_set = True
        self.initialize()


