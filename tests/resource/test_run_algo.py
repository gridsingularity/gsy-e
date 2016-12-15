import random
from d3a.models.resource.run_algo import RunSchedule, RunScheduleLimit

# one tick per sec
ticks_per_bid = 15

# bids for next 2 hours, 15 min each, price in cents
bids = [0.0028, 0.0042, 0.0056, 0.0084, 0.0028, 0.0014, 0.0014, 0.0014]

# power used by appliance in this range
run_usage = (0.7,1.0)


def gen_run_cycle(cycle_width_ticks: int):
    cycle = []

    # Generate appliance power usage randomly between power ranges.
    for i in range(0, cycle_width_ticks):
        cycle.append(random.uniform(run_usage[0], run_usage[1]))

    return cycle


def gen_run_schedule_obj(cycle_width_ticks, cycles_to_run, skip):
    return RunSchedule(bids, gen_run_cycle(cycle_width_ticks), ticks_per_bid, cycles_to_run, skip)


def gen_run_run_schedule_limit(cycle_width_ticks, limit, cycles_to_run, skip):
    return RunScheduleLimit(bids, gen_run_cycle(cycle_width_ticks), ticks_per_bid, limit, cycles_to_run, skip)


def test_global_min_cost_init():
    cycle_to_run = 2
    min_cost_obj = gen_run_schedule_obj(ticks_per_bid, cycle_to_run, 0)

    # assert len(min_cost_obj.normalized_run_cycle) == cycle_to_run * len(min_cost_obj.cycle)
    assert len(min_cost_obj.normalized_bids) == ticks_per_bid * len(bids)


def test_get_min_cost_pass_one():
    cycle_to_run = 2
    min_cost_obj = gen_run_schedule_obj(ticks_per_bid, cycle_to_run, 0)
    calc_min_cost = 0

    for sample in min_cost_obj.cycle:
        calc_min_cost += sample * float(0.0014)

    gen_min_cost = min_cost_obj.get_min_cost()

    print("calculated min cost: {} generated min cost: {}".format(calc_min_cost, gen_min_cost))

    assert int(gen_min_cost) == int(calc_min_cost)


def test_get_run_schedule():
    cycle_to_run = 2
    min_cost_obj = gen_run_schedule_obj(ticks_per_bid, cycle_to_run, 0)

    assert len(min_cost_obj.get_run_schedule()) == cycle_to_run


def test_set_cost_limit():
    cycle_to_run = 2
    skip_cycles = 2
    limit = 0.00
    min_cost_obj = gen_run_run_schedule_limit(ticks_per_bid, cycle_to_run, limit, skip_cycles)

    assert len(min_cost_obj.get_run_schedule()) == (cycle_to_run - skip_cycles)

