from behave import given
from behave import when
from behave import then
import os
import importlib
import glob
import shutil


@given('we have a scenario named {scenario}')
def scenario_check(context, scenario):
    assert importlib.util.find_spec("d3a")
    scenario_file = "./src/d3a/setup/{}.py".format(scenario)
    if not os.path.isfile(scenario_file):
        raise FileExistsError("File not found: {}".format(scenario_file))


@given('d3a is installed')
def install_check(context):
    assert importlib.util.find_spec("d3a") is not None


@when('we run the d3a simulation with {scenario}')
def run_sim(context, scenario):

    context.export_path = os.path.join("./d3a-simulation", "integration_tests", scenario)
    if os.path.isdir(context.export_path):
        shutil.rmtree(context.export_path)
    os.makedirs(context.export_path, exist_ok=True)
    os.system("d3a -l ERROR run -d 2h --setup={scenario} --export --export-path={export_path} "
              "--exit-on-finish".format(export_path=context.export_path, scenario=scenario))


@then('the results are tested for {scenario}')
def test_data(context, scenario):

    data_fn = "grid.csv"
    sim_data_csv = glob.glob(os.path.join(context.export_path, "*", data_fn))

    if len(sim_data_csv) != 1:
        print(os.path.join(context.export_path, "*", data_fn))
        raise FileExistsError("Not found in {path}: {file} ".format(path=context.export_path,
                                                                    file=data_fn))
    else:
        print(sim_data_csv[0])
    # TODO: check the csv data for valid data
