import os
import importlib
import glob
from pendulum.interval import Interval
from behave import given
from behave import when
from behave import then

from d3a.models.config import SimulationConfig
from d3a.simulation import Simulation


@given('we have a scenario named {scenario}')
def scenario_check(context, scenario):
    scenario_file = "./src/d3a/setup/{}.py".format(scenario)
    if not os.path.isfile(scenario_file):
        raise FileExistsError("File not found: {}".format(scenario_file))


@given('d3a is installed')
def install_check(context):
    assert importlib.util.find_spec("d3a") is not None


@when('we run the d3a simulation on console with {scenario}')
def run_sim_console(context, scenario):
    context.export_path = os.path.join(context.simdir, scenario)
    os.makedirs(context.export_path, exist_ok=True)
    os.system("d3a -l FATAL run -d 2h --setup={scenario} --export --export-path={export_path} "
              "--exit-on-finish".format(export_path=context.export_path, scenario=scenario))


@then('we test the export functionality of {scenario}')
def test_export_data_csv(context, scenario):
    data_fn = "grid.csv"
    sim_data_csv = glob.glob(os.path.join(context.export_path, "*", data_fn))
    if len(sim_data_csv) != 1:
        raise FileExistsError("Not found in {path}: {file} ".format(path=context.export_path,
                                                                    file=data_fn))


@when('we run the d3a simulation with {scenario} [{duration}, {slot_length}, {tick_length}]')
def run_sim(context, scenario, duration, slot_length, tick_length):

    simulation_config = SimulationConfig(Interval(hours=int(duration)),
                                         Interval(minutes=int(slot_length)),
                                         Interval(seconds=int(tick_length)), market_count=5)

    slowdown = 0
    seed = 0
    paused = False
    pause_after = Interval()
    repl = False
    export = False
    export_path = None
    reset_on_finish = False
    reset_on_finish_wait = Interval()
    exit_on_finish = True
    exit_on_finish_wait = Interval()

    api_url = "http://localhost:5000/api"
    simulation = Simulation(
        scenario,
        simulation_config,
        slowdown,
        seed,
        paused,
        pause_after,
        repl,
        export,
        export_path,
        reset_on_finish,
        reset_on_finish_wait,
        exit_on_finish,
        exit_on_finish_wait,
        api_url
    )
    simulation.run()

    context.simulation = simulation


@then('we test the output of the simulation of '
      '{scenario} [{duration}, {slot_length}, {tick_length}]')
def test_output(context, scenario, duration, slot_length, tick_length):

    # Check if simulation ran through
    # (check if number of last slot is the maximal number of slots):
    no_of_slots = (int(duration) * 60 / int(slot_length)) + 1
    assert no_of_slots == context.simulation.area.current_slot
    # TODO: Implement more sophisticated tests for success of simulation
