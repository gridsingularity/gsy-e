import random
from d3a.models.resource.run_algo import RunSchedule, RunScheduleLimit

# one tick per sec
ticks_per_bid = 15*60

# bids for next 2 hours, 15 min each, price in cents
bids = [0.0028, 0.0042, 0.0056, 0.0084, 0.0028, 0.0014, 0.0014, 0.0014]

# power used by appliance in this range
run_usage = (0.7, 1.0)


def gen_run_cycle(cycle_width_ticks: int) -> list:
    """
    Randomly generates power consumption profile for an appliance
    :param cycle_width_ticks: Duration for which an appliance will run, in number of ticks
    :return: List
    """
    cycle = []

    # Generate appliance power usage randomly between power ranges.
    for i in range(0, cycle_width_ticks):
        cycle.append(random.uniform(run_usage[0], run_usage[1]))

    return cycle


def gen_schedule_obj(cycle_width_ticks, cycles_to_run, skip):
    """
    Generates an object to minimize running cost without any price limit.
    :param cycle_width_ticks:
    :param cycles_to_run:
    :param skip:
    :return:
    """
    return RunSchedule(bids, gen_run_cycle(cycle_width_ticks), ticks_per_bid, cycles_to_run, skip)


def gen_schedule_limit(cycle_width_ticks, limit, cycles_to_run, skip):
    """
    Generates an object to minimize running cost with a price limit.
    :param cycle_width_ticks:
    :param limit:
    :param cycles_to_run:
    :param skip:
    :return:
    """
    return RunScheduleLimit(bids, gen_run_cycle(cycle_width_ticks), ticks_per_bid, limit, cycles_to_run, skip)


def gen_schedule_obj_max(cycle_width_ticks, cycles_to_run, skip):
    """
    Generates an object to maximize running cost for an appliance
    :param cycle_width_ticks:
    :param cycles_to_run:
    :param skip:
    :return:
    """
    return RunSchedule(bids, gen_run_cycle(cycle_width_ticks), ticks_per_bid, cycles_to_run, skip, True)


def test_schedule_init():
    """
    Test if bids are normalized to same unit time unit as that of appliance power usage unit.
    """
    cycle_to_run = 2
    min_cost_obj = gen_schedule_obj(ticks_per_bid, cycle_to_run, 0)

    # assert len(min_cost_obj.normalized_run_cycle) == cycle_to_run * len(min_cost_obj.cycle)
    assert len(min_cost_obj.normalized_bids) == ticks_per_bid * len(bids)


def test_get_min_cost():
    """
    Test to verify the run cost returned by algo is indeed minimum run cost for appliance.
    """
    cycle_to_run = 2
    min_cost_obj = gen_schedule_obj(ticks_per_bid, cycle_to_run, 0)
    calc_min_cost = 0

    for sample in min_cost_obj.cycle:
        calc_min_cost += sample * float(0.0014)

    gen_min_cost = min_cost_obj.cost[0][0]

    print("calculated min cost: {} generated min cost: {}".format(calc_min_cost, gen_min_cost))

    assert gen_min_cost == round(calc_min_cost, 10)


def test_get_optimal_schedule():
    """
    Test to verify that the algo returns asked set if points to run appliances.
    """
    cycle_to_run = 2
    min_cost_obj = gen_schedule_obj(ticks_per_bid, cycle_to_run, 0)

    assert len(min_cost_obj.get_optimal_schedule()) == cycle_to_run


def test_get_run_schedule():
    cycle_to_run = 2
    min_cost_obj = gen_schedule_obj(ticks_per_bid, cycle_to_run, 0)

    assert len(min_cost_obj.get_run_schedule()) == (len(bids) * ticks_per_bid)


def test_set_cost_limit():
    """
    Test to verify the algo returns fewer number of run cycles if a price limit is placed
    """
    cycle_to_run = 4
    skip_cycles = 1
    limit = 4.00
    min_cost_obj = gen_schedule_limit(ticks_per_bid, cycle_to_run, limit, skip_cycles)

    assert len(min_cost_obj.get_optimal_schedule()) == (cycle_to_run - skip_cycles)


# def test_reverse_priority_queue():
#     """
#     Test to verify the algo returns max running cost for an appliance once maximize flag is set.
#     """
#     cycle_to_run = 1
#
#     max_cost_obj = gen_schedule_obj_max(ticks_per_bid, cycle_to_run, 0)
#
#     assert max_cost_obj.cost[0][0] > max_cost_obj.cost[max_cost_obj.run_window][0]

