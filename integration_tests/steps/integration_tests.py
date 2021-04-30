"""
Copyright 2018 Grid Singularity
This file is part of D3A.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
import uuid
import json
import os
import importlib
import logging
import glob
import traceback
from math import isclose
from copy import deepcopy
from pendulum import duration, today, from_format
from behave import given, when, then
from deepdiff import DeepDiff

from d3a_interface.read_user_profile import read_arbitrary_profile, InputProfileTypes, \
    default_profile_dict
from d3a_interface.constants_limits import ConstSettings, GlobalConfig
from d3a_interface.utils import convert_W_to_Wh, convert_W_to_kWh, convert_kW_to_kWh, \
    get_area_name_uuid_mapping
from d3a.models.config import SimulationConfig
from d3a.d3a_core.simulation import Simulation
from d3a.d3a_core.util import d3a_path
from d3a.constants import DATE_TIME_FORMAT, DATE_FORMAT, TIME_ZONE
from d3a import constants


TODAY_STR = today(tz=TIME_ZONE).format(DATE_FORMAT)
ACCUMULATED_KEYS_LIST = ["Accumulated Trades", "External Trades", "Totals", "Market Fees"]


@given('we have a scenario named {scenario}')
def scenario_check(context, scenario):
    if "." in scenario:
        scenario = scenario.replace(".", "/")
    scenario_file = "./src/d3a/setup/{}.py".format(scenario)
    if not os.path.isfile(scenario_file):
        raise FileExistsError("File not found: {}".format(scenario_file))


@given('d3a is installed')
def install_check(context):
    assert importlib.util.find_spec("d3a") is not None


@given('a {device} profile hourly dict as input to predefined load')
def hour_profile(context, device):
    context._device_profile = {
        1: 100,
        2: 200,
        4: 50,
        8: 80,
        10: 120,
        13: 20,
        16: 70,
        17: 15,
        19: 45,
        22: 100
    }


@given('a {device} profile string as input to predefined load')
def json_string_profile(context, device):
    context._device_profile_dict = {today(tz=TIME_ZONE).add(hours=hour): 100
                                    for hour in range(10)}
    context._device_profile_dict.update({today(tz=TIME_ZONE).add(hours=hour): 50
                                         for hour in range(10, 20)})
    context._device_profile_dict.update({today(tz=TIME_ZONE).add(hours=hour): 25
                                         for hour in range(20, 25)})

    profile = "{"
    for i in range(24):
        if i < 10:
            profile += f"\"{i:02}:00\": 100, "
        elif 10 <= i < 20:
            profile += f"\"{i:02}:00\": 50, "
        else:
            profile += f"\"{i:02}:00\": 25, "
    profile += "}"
    context._device_profile = profile


@given('we have a profile of market_maker_rate for {scenario}')
def hour_profile_of_market_maker_rate(context, scenario):
    import importlib
    from d3a_interface.read_user_profile import InputProfileTypes
    setup_file_module = importlib.import_module("d3a.setup.{}".format(scenario))
    context._market_maker_rate = \
        read_arbitrary_profile(InputProfileTypes.IDENTITY, setup_file_module.market_maker_rate)

    assert context._market_maker_rate is not None


@given('a PV profile csv as input to predefined PV')
def pv_csv_profile(context):
    context._device_profile = os.path.join(d3a_path, 'resources', 'Solar_Curve_W_cloudy.csv')


@given('the scenario includes a predefined PV')
def pv_profile_scenario(context):
    predefined_pv_scenario = {
        "name": "Grid",
        "children": [
            {
                "name": "Commercial Energy Producer",
                "type": "CommercialProducer",
                "energy_rate": 15.5
            },
            {
                "name": "House 1",
                "children": [
                    {
                        "name": "H1 Load",
                        "type": "LoadHours",
                        "avg_power_W": 400,
                        "hrs_per_day": 24
                    },
                    {
                        "name": "H1 PV",
                        "type": "PVProfile",
                        "panel_count": 1,
                        "power_profile": context._device_profile
                    }
                ]
            },
            {
                "name": "House 2",
                "children": [
                    {
                        "name": "H2 Storage",
                        "type": "Storage",
                        "battery_capacity_kWh": 12.5,
                    }
                ]
            }
        ]
    }
    context._settings = SimulationConfig(tick_length=duration(seconds=60),
                                         slot_length=duration(minutes=60),
                                         sim_duration=duration(hours=23),
                                         market_count=4,
                                         cloud_coverage=0,
                                         market_maker_rate=30,
                                         external_connection_enabled=False)
    context._settings.area = predefined_pv_scenario


@given('the scenario includes a predefined load that will not be unmatched')
def load_profile_scenario(context):
    predefined_load_scenario = {
      "name": "Grid",
      "children": [
        {
          "name": "Commercial Energy Producer",
          "type": "CommercialProducer",
          "energy_rate": 15.5
        },
        {
          "name": "House 1",
          "children": [
            {
              "name": "H1 Load",
              "type": "LoadProfile",
              "daily_load_profile": context._device_profile
            },
            {
              "name": "H1 PV",
              "type": "PV",
              "panel_count": 3
            }
          ]
        },
        {
          "name": "House 2",
          "children": [
            {
              "name": "H2 Storage",
              "type": "Storage",
              "battery_capacity_kWh": 12.5,
            }
          ]
        }
      ]
    }
    context._settings = SimulationConfig(tick_length=duration(seconds=60),
                                         slot_length=duration(minutes=60),
                                         sim_duration=duration(hours=24),
                                         market_count=4,
                                         cloud_coverage=0,
                                         market_maker_rate=30,
                                         external_connection_enabled=False)
    context._settings.area = predefined_load_scenario


@given('d3a uses an {market_type} market')
def one_sided_market(context, market_type):
    from d3a_interface.constants_limits import ConstSettings
    if market_type == "one-sided":
        ConstSettings.IAASettings.MARKET_TYPE = 1
    elif market_type == "two-sided-pay-as-bid":
        ConstSettings.IAASettings.MARKET_TYPE = 2
        ConstSettings.IAASettings.BID_OFFER_MATCH_TYPE = 2
    elif market_type == "two-sided-pay-as-clear":
        ConstSettings.IAASettings.MARKET_TYPE = 2
        ConstSettings.IAASettings.BID_OFFER_MATCH_TYPE = 2


@given('d3a dispatches events from top to bottom')
def dispatch_top_bottom(context):
    import d3a.constants
    d3a.constants.DISPATCH_EVENTS_BOTTOM_TO_TOP = False


@given('d3a dispatches events from bottom to top')
def dispatch_bootom_top(context):
    import d3a.constants
    d3a.constants.DISPATCH_EVENTS_BOTTOM_TO_TOP = True


@given('the past markets are kept in memory')
def past_markets_in_memory(context):
    constants.D3A_TEST_RUN = True


@given('the minimum offer age is {min_offer_age}')
def set_min_offer_age(context, min_offer_age):
    ConstSettings.IAASettings.MIN_OFFER_AGE = int(min_offer_age)


@when('the simulation is running')
def running_the_simulation(context):

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.ERROR)

    seed = 0
    paused = False
    pause_after = duration()
    repl = False
    no_export = True
    export_path = None
    export_subdir = None
    context.simulation = Simulation(
        'json_arg',
        context._settings,
        None,
        seed,
        paused,
        pause_after,
        repl,
        no_export,
        export_path,
        export_subdir,
    )
    context.simulation.run()


@when('we run the d3a simulation on console with {scenario} for {hours} hrs')
def run_sim_console(context, scenario, hours):
    context.export_path = os.path.join(context.simdir, scenario)
    os.makedirs(context.export_path, exist_ok=True)
    os.system("d3a -l FATAL run -d {hours}h -t 60s -s 60m --setup={scenario} "
              "--export-path={export_path}"
              .format(export_path=context.export_path, scenario=scenario, hours=hours))


@when('we run the d3a simulation on console with {scenario} for {hours} hrs '
      '({slot_length}, {tick_length})')
def run_sim_console_decreased_tick_slot_length(context, scenario, hours, slot_length, tick_length):
    context.export_path = os.path.join(context.simdir, scenario)
    os.makedirs(context.export_path, exist_ok=True)
    os.system(f"d3a -l FATAL run -d {hours}h -t {tick_length}s -s {slot_length}m "
              f"--seed 0 --setup={scenario} --export-path={context.export_path}")


@when('we run the d3a simulation with compare-alt-pricing flag with {scenario}')
def run_sim_console_alt_price(context, scenario):
    context.export_path = os.path.join(context.simdir, scenario)
    os.makedirs(context.export_path, exist_ok=True)
    os.system("d3a -l FATAL run -d 2h -t 15s --setup={scenario} --export-path={export_path} "
              "--compare-alt-pricing".format(export_path=context.export_path, scenario=scenario))


@when('we run the d3a simulation on console with {scenario} for {hours} hrs slot_length: '
      '{slot_length}m, tick_length: {tick_length}s and markets: {market_count}')
def run_simulation_via_console(context, scenario, hours, slot_length,
                               tick_length, market_count):
    context.export_path = os.path.join(context.simdir, scenario)
    os.makedirs(context.export_path, exist_ok=True)
    os.system(f"d3a -l FATAL run -d {hours}h -t {tick_length}s -s {slot_length}m "
              f"-m {market_count} --seed 0 --setup={scenario} --export-path={context.export_path}")


@when('we run the d3a simulation with cloud_coverage [{cloud_coverage}] and {scenario}')
def run_sim_with_config_setting(context, cloud_coverage, scenario):

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.ERROR)

    simulation_config = SimulationConfig(duration(hours=int(24)),
                                         duration(minutes=int(60)),
                                         duration(seconds=int(60)),
                                         market_count=4,
                                         cloud_coverage=int(cloud_coverage),
                                         external_connection_enabled=False)

    seed = 0
    paused = False
    pause_after = duration()
    repl = False
    no_export = True
    export_path = None
    export_subdir = None
    context.simulation = Simulation(
        scenario,
        simulation_config,
        None,
        seed,
        paused,
        pause_after,
        repl,
        no_export,
        export_path,
        export_subdir,
    )
    context.simulation.run()


@when('we run simulation on console with default settings file')
def run_d3a_with_settings_file(context):
    context.export_path = os.path.join(context.simdir, "default")
    os.makedirs(context.export_path, exist_ok=True)
    os.system("d3a -l FATAL run -g {settings_file} --export-path={export_path} "
              "--setup default_2a".format(export_path=context.export_path,
                                          settings_file=os.path.join(d3a_path, "setup",
                                                                     "d3a-settings.json")))


@when('the reported price energy day results are saved')
def step_impl(context):
    raw_results = context.simulation.endpoint_buffer.results_handler.all_raw_results
    price_energy_day = raw_results["price_energy_day"]
    context.price_energy_day = deepcopy(price_energy_day)


@when('the reported {bill_type} bills are saved')
def save_reported_bills(context, bill_type):
    raw_results = context.simulation.endpoint_buffer.results_handler.all_raw_results
    ui_results = context.simulation.endpoint_buffer.results_handler.all_ui_results
    if bill_type == "energy":
        context.energy_bills = deepcopy(raw_results["bills"])
        context.energy_bills_redis = deepcopy(ui_results["bills"])
    elif bill_type == "cumulative":
        context.energy_bills = deepcopy(raw_results["cumulative_bills"])


@when('the past markets are not kept in memory')
def past_markets_not_in_memory(context):
    # d3a has to be set to publish the full results:
    ConstSettings.GeneralSettings.REDIS_PUBLISH_FULL_RESULTS = True

    constants.D3A_TEST_RUN = False


@then('we test the export functionality of {scenario}')
def test_export_data_csv(context, scenario):
    data_fn = "grid.csv"
    sim_data_csv = glob.glob(os.path.join(context.export_path, "*", data_fn))
    if len(sim_data_csv) != 1:
        raise FileExistsError("Not found in {path}: {file} ".format(path=context.export_path,
                                                                    file=data_fn))


@then('the export functionality of supply/demand curve is tested')
def test_export_supply_demand_curve(context):
    sim_data_csv = glob.glob(os.path.join(context.export_path, "*", "plot", "mcp"))
    if len(sim_data_csv) != 1:
        raise FileExistsError("Not found in {path}".format(path=context.export_path))


@then('we test the export of with compare-alt-pricing flag')
def test_export_data_csv_alt_pricing(context):
    data_fn = "grid.csv"
    from d3a.d3a_core.export import alternative_pricing_subdirs
    for subdir in alternative_pricing_subdirs.values():
        sim_data_csv = glob.glob(os.path.join(context.export_path, "*", subdir, data_fn))
        if len(sim_data_csv) != 1:
            raise FileExistsError(f"Not found in {context.export_path}: {data_fn}")


@then('there are nonempty files with offers ({with_or_without} balancing offers) '
      'and bids for every area')
def nonempty_test_offer_bid_files(context, with_or_without):
    test_offer_bid_files(context, with_or_without, True)


@then('there are files with offers ({with_or_without} balancing offers) '
      'and bids for every area')
def test_offer_bid_files(context, with_or_without, nonempty=False):
    base_path = os.path.join(context.export_path, "*")
    file_list = [os.path.join(base_path, 'grid-offers.csv'),
                 os.path.join(base_path, 'grid-bids.csv'),
                 os.path.join(base_path, 'grid', 'house-1-offers.csv'),
                 os.path.join(base_path, 'grid', 'house-1-bids.csv'),
                 os.path.join(base_path, 'grid', 'house-2-offers.csv'),
                 os.path.join(base_path, 'grid', 'house-2-bids.csv')]

    if with_or_without == "with":
        file_list += [os.path.join(base_path, 'grid-balancing-offers.csv'),
                      os.path.join(base_path, 'grid', 'house-1-balancing-offers.csv'),
                      os.path.join(base_path, 'grid', 'house-2-balancing-offers.csv')]

    line_count_limit = 2 if nonempty else 1
    assert all(len(glob.glob(f)) == 1 for f in file_list)
    assert all(len(open(glob.glob(f)[0]).readlines()) > line_count_limit
               for f in file_list)


@then('aggregated result files are exported')
def test_aggregated_result_files(context):
    base_path = os.path.join(context.export_path, "*", "aggregated_results")
    file_list = [os.path.join(base_path, 'bills.json'),
                 os.path.join(base_path, 'const_settings.json'),
                 os.path.join(base_path, 'cumulative_grid_trades.json'),
                 os.path.join(base_path, 'job_id.json'),
                 os.path.join(base_path, 'kpi.json'),
                 os.path.join(base_path, 'price_energy_day.json'),
                 os.path.join(base_path, 'random_seed.json'),
                 os.path.join(base_path, 'status.json')]

    assert all(len(glob.glob(f)) == 1 for f in file_list)
    assert all(len(open(glob.glob(f)[0]).readlines()) > 0 for f in file_list)


@then('we test that cloud coverage [{cloud_coverage}] and market_maker_rate are parsed correctly')
def test_simulation_config_parameters(context, cloud_coverage):
    assert context.simulation.simulation_config.cloud_coverage == int(cloud_coverage)
    day_factor = 24 * 7 if GlobalConfig.IS_CANARY_NETWORK else 24
    assert len(context.simulation.simulation_config.market_maker_rate) == \
        day_factor / context.simulation.simulation_config.slot_length.hours + \
        context.simulation.simulation_config.market_count
    assert len(default_profile_dict().keys()) == len(context.simulation.simulation_config.
                                                     market_maker_rate.keys())
    assert context.simulation.simulation_config.market_maker_rate[
               from_format(f"{TODAY_STR}T01:00", DATE_TIME_FORMAT)] == 0
    assert context.simulation.simulation_config.market_maker_rate[from_format(
        f"{TODAY_STR}T12:00", DATE_TIME_FORMAT)] == context._market_maker_rate[
        from_format(f"{TODAY_STR}T11:00", DATE_TIME_FORMAT)]
    assert context.simulation.simulation_config.market_maker_rate[from_format(
        f"{TODAY_STR}T23:00", DATE_TIME_FORMAT)] == context._market_maker_rate[
        from_format(f"{TODAY_STR}T22:00", DATE_TIME_FORMAT)]


@when('a simulation is created for scenario {scenario}')
def create_sim_object(context, scenario):
    simulation_config = SimulationConfig(duration(hours=int(12)),
                                         duration(minutes=int(60)),
                                         duration(seconds=int(60)),
                                         market_count=1,
                                         cloud_coverage=0,
                                         market_maker_rate=30,
                                         start_date=today(tz=TIME_ZONE),
                                         external_connection_enabled=False)

    context.simulation = Simulation(
        scenario, simulation_config, None, 0, False, duration(), False, False, None, None,
        "1234", False
    )


@when('the method {method} is registered')
def monkeypatch_ctrl_callback(context, method):
    context.ctrl_callback_call_count = 0

    def method_callback():
        context.ctrl_callback_call_count += 1
    setattr(context.simulation, method, method_callback)


@when('the configured simulation is running')
def configd_sim_run(context):
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.ERROR)
    context.simulation.run()


@when('a message is sent on {channel}')
def message_on_channel(context, channel):
    context.ctrl_publish_callback_call_count = 0
    data = {"transaction_id": str(uuid.uuid4())}
    payload = {"data": json.dumps(data)}

    def mock_publish_json(*args):
        context.ctrl_publish_callback_call_count += 1

    context.simulation.redis_connection.publish_json = mock_publish_json
    context.simulation.redis_connection._sub_callback_dict[channel](payload)


@when('the simulation is able to transmit intermediate results')
def interm_results(context):
    context.interm_results_count = 0

    def interm_res_count(_):
        context.interm_results_count += 1
    context.simulation.redis_connection.publish_intermediate_results = interm_res_count


@when('the simulation is able to transmit final results')
def final_results(context):
    context.final_results_count = 0

    def final_res_count(_):
        context.final_results_count += 1
    context.simulation.redis_connection.publish_results = final_res_count


@when('the redis_connection is enabled')
def transmit_zipped_results(context):
    context.simulation.redis_connection.is_enabled = lambda: True


@then('intermediate results are transmitted on every slot')
def interm_res_report(context):
    # Add an extra result for the start of the simulation
    assert context.interm_results_count == 12


@then('final results are transmitted once')
def final_res_report(context):
    assert context.final_results_count == 1


@then('{method} is called')
def method_called(context, method):
    assert context.ctrl_callback_call_count == 1
    assert context.ctrl_publish_callback_call_count == 1


@given('the min offer age is set to {min_offer_age} tick')
def min_offer_age_nr_ticks(context, min_offer_age):
    ConstSettings.IAASettings.MIN_OFFER_AGE = int(min_offer_age)


@given('the min bid age is set to {min_bid_age} ticks')
def min_bid_age_nr_ticks(context, min_bid_age):
    ConstSettings.IAASettings.MIN_BID_AGE = int(min_bid_age)


@when('we run a multi-day d3a simulation with {scenario} [{start_date}, {total_duration}, '
      '{slot_length}, {tick_length}]')
def run_sim_multiday(context, scenario, start_date, total_duration, slot_length, tick_length):

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.ERROR)
    if start_date == "None":
        start_date = today(tz=TIME_ZONE)
    else:
        start_date = from_format(start_date, DATE_FORMAT)

    simulation_config = SimulationConfig(duration(hours=int(total_duration)),
                                         duration(minutes=int(slot_length)),
                                         duration(seconds=int(tick_length)),
                                         market_count=1,
                                         cloud_coverage=0,
                                         market_maker_rate=30,
                                         start_date=start_date,
                                         external_connection_enabled=False)

    seed = 0
    paused = False
    pause_after = duration()
    repl = False
    no_export = True
    export_path = None
    export_subdir = None
    context.simulation = Simulation(
        scenario,
        simulation_config,
        None,
        seed,
        paused,
        pause_after,
        repl,
        no_export,
        export_path,
        export_subdir,
    )
    context.simulation.run()


@when("we run the simulation with setup file {scenario} with two different market_counts")
def run_sim_market_count(context, scenario):
    run_sim(context, scenario, 24, 60, 60, market_count=1)
    context.simulation_1 = context.simulation

    run_sim(context, scenario, 24, 60, 60, market_count=4)
    context.simulation_4 = context.simulation


@given('export {flag}')
@when('export {flag}')
def export_logic(context, flag):
    context.no_export = True if flag == 'isnt_needed' else False


@when('we run the simulation with setup file {scenario} and parameters '
      '[{total_duration}, {slot_length}, {tick_length}, {market_count}]')
@then('we run the simulation with setup file {scenario} and parameters '
      '[{total_duration}, {slot_length}, {tick_length}, {market_count}]')
def run_sim(context, scenario, total_duration, slot_length, tick_length, market_count):

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.ERROR)

    simulation_config = SimulationConfig(duration(hours=int(total_duration)),
                                         duration(minutes=int(slot_length)),
                                         duration(seconds=int(tick_length)),
                                         market_count=int(market_count),
                                         cloud_coverage=0,
                                         market_maker_rate=30,
                                         external_connection_enabled=False)

    seed = 0
    paused = False
    pause_after = duration()
    repl = False
    export_subdir = None
    context.export_path = os.path.join(context.simdir, scenario)
    os.makedirs(context.export_path, exist_ok=True)
    try:
        context.simulation = Simulation(
            scenario,
            simulation_config,
            None,
            seed,
            paused,
            pause_after,
            repl,
            context.no_export,
            context.export_path,
            export_subdir,
        )
        context.simulation.run()
    except Exception as er:
        if context.raise_exception_when_running_sim:
            root_logger.critical(f"Error reported when running the simulation: {er}")
            root_logger.critical(f"Traceback: {traceback.format_exc()}")
            raise Exception(er)
        else:
            context.sim_error = er


@then('we test the output of the simulation of '
      '{scenario} [{sim_duration}, {slot_length}, {tick_length}]')
def test_output(context, scenario, sim_duration, slot_length, tick_length):
    from integration_tests.steps.integration_tests import get_simulation_raw_results
    get_simulation_raw_results(context)

    # (check if simulation successfully finished):
    assert len(context.raw_sim_data.keys()) == 24
    if scenario == "default":
        assert {"Street 1", "S1 House 1", "S1 H1 Load"}.\
            issubset(set(context.name_uuid_map.keys()))
        for time_slot, core_stats in context.raw_sim_data.items():
            assert 'load_profile_kWh' in core_stats[context.name_uuid_map['S1 H1 Load']].keys()


@then('the energy bills report the correct accumulated traded energy price')
def test_accumulated_energy_price(context):
    raw_results = context.simulation.endpoint_buffer.results_handler.all_raw_results
    bills = raw_results["bills"]
    for bills_key in [c for c in bills.keys() if "Accumulated Trades" in c]:
        extern_trades = bills[bills_key]["External Trades"]
        assert extern_trades["total_energy"] == extern_trades["bought"] - extern_trades["sold"]
        # Checks if "Accumulated Trades" got accumulated correctly:
        house_bill = bills[bills_key]["Accumulated Trades"]["earned"] - \
            bills[bills_key]["Accumulated Trades"]["spent"]
        area_net_traded_energy_price = \
            sum([v["earned"] - v["spent"] for k, v in bills[bills_key].items()
                if k not in ACCUMULATED_KEYS_LIST])
        assert isclose(area_net_traded_energy_price, house_bill, rel_tol=1e-02), \
            f"{bills_key} area: {area_net_traded_energy_price} house {house_bill}"
        # Checks if spent+market_fee-earned=total_cost is true for all accumulated members
        for accumulated_section in ACCUMULATED_KEYS_LIST:
            assert isclose(bills[bills_key][accumulated_section]["spent"]
                           + bills[bills_key][accumulated_section]["market_fee"]
                           - bills[bills_key][accumulated_section]["earned"],
                           bills[bills_key][accumulated_section]["total_cost"],  abs_tol=1e-10)
        #
        for key in ["spent", "earned", "total_cost", "sold", "bought", "total_energy"]:
            assert isclose(bills[bills_key]["Accumulated Trades"][key] +
                           bills[bills_key]["External Trades"][key] +
                           bills[bills_key]["Market Fees"][key],
                           bills[bills_key]["Totals"][key], abs_tol=1e-10)
        assert isclose(bills[bills_key]["Totals"]["total_cost"], 0, abs_tol=1e-10)


@then('the traded energy report the correct accumulated traded energy')
def test_accumulated_energy(context):
    raw_results = context.simulation.endpoint_buffer.results_handler.all_raw_results
    bills = raw_results["bills"]
    if "Cell Tower" not in bills:
        return
    cell_tower_net = bills["Cell Tower"]["sold"] - bills["Cell Tower"]["bought"]
    net_energy = cell_tower_net
    for house_key in ["House 1", "House 2"]:
        house_net = bills[house_key]["Accumulated Trades"]["sold"] - \
                    bills[house_key]["Accumulated Trades"]["bought"] + \
                    bills[house_key]["Totals"]["bought"] - \
                    bills[house_key]["Totals"]["sold"]

        area_net_energy = \
            sum([v["sold"] - v["bought"] for k, v in bills[house_key].items()
                 if k not in ACCUMULATED_KEYS_LIST])
        assert isclose(area_net_energy, house_net, rel_tol=1e-02)
        net_energy += house_net

    assert isclose(net_energy, 0, abs_tol=1e-10)


@then('the energy bills report the correct external traded energy and price')
def test_external_trade_energy_price(context):
    # TODO: Deactivating this test for now, because it will fail due to D3ASIM-1887.
    # Please activate the test when implementing the aforementioned bug.
    return

    raw_results = context.simulation.endpoint_buffer.results_handler.all_raw_results
    current_trades = raw_results["cumulative_grid_trades"]
    bills = raw_results["bills"]
    houses = [child for child in context.simulation.area.children
              if child.name in ["House 1", "House 2"]]
    for house in houses:
        house_sold = bills[house.name]["External Trades"]["sold"]
        house_bought = bills[house.name]["External Trades"]["bought"]

        external_trade_sold = sum([
            k["energy"]
            for k in current_trades[house.uuid][-1]["bars"]
            if "External sources" in k["energyLabel"] and k["energy"] < 0
        ])

        external_trade_bought = sum([
            k["energy"]
            for k in current_trades[house.uuid][-1]["bars"]
            if "External sources" in k["energyLabel"] and k["energy"] >= 0
        ])

        assert isclose(-external_trade_sold, house_sold, abs_tol=1e-3)
        assert isclose(external_trade_bought, house_bought, abs_tol=1e-3)


@then('the cumulative energy bills for each area are the sum of its children')
def cumulative_bills_sum(context):
    ui_results = context.simulation.endpoint_buffer.results_handler.all_ui_results
    cumulative_bills = ui_results["cumulative_bills"]
    bills = ui_results["bills"]

    def assert_area_cumulative_bills(area):
        area_bills = cumulative_bills[area.uuid]
        if len(area.children) == 0:
            estimated_total = area_bills["spent_total"] - area_bills["earned"] + \
                              area_bills["penalties"]
            assert isclose(area_bills["total"], estimated_total, abs_tol=0.0011)
            assert isclose(bills[area.uuid]["spent"] + bills[area.uuid]["market_fee"],
                           cumulative_bills[area.uuid]["spent_total"], abs_tol=0.0011)
            return
        child_uuids = [child.uuid for child in area.children]
        assert isclose(area_bills["spent_total"],
                       sum(cumulative_bills[uuid]["spent_total"] for uuid in child_uuids),
                       abs_tol=0.0011)
        assert isclose(area_bills["earned"],
                       sum(cumulative_bills[uuid]["earned"] for uuid in child_uuids),
                       abs_tol=0.0011)
        assert isclose(area_bills["penalties"],
                       sum(cumulative_bills[uuid]["penalties"] for uuid in child_uuids),
                       abs_tol=0.0011)
        assert isclose(area_bills["total"],
                       sum(cumulative_bills[uuid]["total"] for uuid in child_uuids),
                       abs_tol=0.0011)

        for child in area.children:
            assert_area_cumulative_bills(child)

    assert_area_cumulative_bills(context.simulation.area)


def generate_area_uuid_map(sim_area, results):
    results[sim_area.slug] = sim_area.uuid
    for child in sim_area.children:
        results = generate_area_uuid_map(child, results)
    return results


@then('the predefined load follows the load profile')
def check_load_profile(context):
    if GlobalConfig.IS_CANARY_NETWORK:
        return
    if isinstance(context._device_profile, str):
        context._device_profile = context._device_profile_dict

    house1 = list(filter(lambda x: x.name == "House 1", context.simulation.area.children))[0]
    load = list(filter(lambda x: x.name == "H1 Load", house1.children))[0]
    for timepoint, energy in load.strategy.state._desired_energy_Wh.items():
        assert energy == convert_W_to_Wh(context._device_profile[timepoint],
                                         load.config.slot_length)


@then('the predefined PV follows the PV profile')
def check_pv_profile(context):
    house1 = list(filter(lambda x: x.name == "House 1", context.simulation.area.children))[0]
    pv = list(filter(lambda x: x.name == "H1 PV", house1.children))[0]
    if pv.strategy._power_profile_index == 0:
        path = os.path.join(d3a_path, "resources/Solar_Curve_W_sunny.csv")
    if pv.strategy._power_profile_index == 1:
        path = os.path.join(d3a_path, "resources/Solar_Curve_W_partial.csv")
    if pv.strategy._power_profile_index == 2:
        path = os.path.join(d3a_path, "resources/Solar_Curve_W_cloudy.csv")
    profile_data = read_arbitrary_profile(
        InputProfileTypes.POWER,
        str(path))
    for timepoint, energy in pv.strategy.state._energy_production_forecast_kWh.items():
        if timepoint in profile_data.keys():
            assert energy == profile_data[timepoint]
        else:
            assert energy == 0


@then('the UserProfile PV follows the PV profile as dict')
def check_user_pv_dict_profile(context):
    house1 = list(filter(lambda x: x.name == "House 1", context.simulation.area.children))[0]
    pv = list(filter(lambda x: x.name == "H1 PV", house1.children))[0]
    from d3a.setup.strategy_tests.user_profile_pv_dict import user_profile
    profile_data = user_profile
    for timepoint, energy in pv.strategy.state._energy_production_forecast_kWh.items():
        if timepoint.hour in profile_data.keys():
            assert energy == convert_W_to_kWh(profile_data[timepoint.hour], pv.config.slot_length)
        else:
            if int(timepoint.hour) > int(list(user_profile.keys())[-1]):
                assert energy == convert_W_to_kWh(user_profile[list(user_profile.keys())[-1]],
                                                  pv.config.slot_length)
            else:
                assert energy == 0


@then('the UserProfile PV follows the PV profile of csv')
def check_pv_csv_profile(context):
    house1 = list(filter(lambda x: x.name == "House 1", context.simulation.area.children))[0]
    pv = list(filter(lambda x: x.name == "H1 PV", house1.children))[0]
    from d3a.setup.strategy_tests.user_profile_pv_csv import user_profile_path
    profile_data = read_arbitrary_profile(
        InputProfileTypes.POWER,
        user_profile_path)
    for timepoint, energy in pv.strategy.state._energy_production_forecast_kWh.items():
        if timepoint in profile_data.keys():
            assert energy == profile_data[timepoint]
        else:
            assert energy == 0


@then('the predefined PV follows the PV profile from the csv')
def check_pv_profile_csv(context):
    house1 = list(filter(lambda x: x.name == "House 1", context.simulation.area.children))[0]
    pv = list(filter(lambda x: x.name == "H1 PV", house1.children))[0]
    input_profile = read_arbitrary_profile(
        InputProfileTypes.POWER,
        context._device_profile)
    produced_energy = {from_format(f'{TODAY_STR}T{k.hour:02}:{k.minute:02}', DATE_TIME_FORMAT): v
                       for k, v in pv.strategy.state._energy_production_forecast_kWh.items()
                       }
    for timepoint, energy in produced_energy.items():
        if timepoint in input_profile:
            assert energy == input_profile[timepoint]
        else:
            assert False


@then('the {plant_name} always sells energy at the defined energy rate')
def test_finite_plant_energy_rate(context, plant_name):
    grid = context.simulation.area
    finite = list(filter(lambda x: x.name == plant_name,
                         grid.children))[0]
    trades_sold = []
    for market in grid.past_markets:
        for trade in market.trades:
            assert trade.buyer is not finite.name
            if trade.seller == finite.name:
                trades_sold.append(trade)
        assert all([isclose(trade.offer.price / trade.offer.energy,
                            finite.strategy.energy_rate[market.time_slot], rel_tol=1e-02)
                    for trade in trades_sold])
        assert len(trades_sold) > 0


@then('the {plant_name} always sells energy at the defined market maker rate')
def test_infinite_plant_energy_rate(context, plant_name):
    grid = context.simulation.area

    market_maker_rate = context.simulation.simulation_config.market_maker_rate
    finite = list(filter(lambda x: x.name == plant_name,
                         grid.children))[0]
    trades_sold = []
    for market in grid.past_markets:
        for trade in market.trades:
            assert trade.buyer is not finite.name
            trade.offer.next_market = market
            if trade.seller == finite.name:
                trades_sold.append(trade)

    assert all([isclose(trade.offer.price / trade.offer.energy,
                        market_maker_rate[trade.offer.next_market.time_slot])
                for trade in trades_sold])
    assert len(trades_sold) > 0


@then('the {plant_name} never produces more power than its max available power')
def test_finite_plant_max_power(context, plant_name):
    grid = context.simulation.area
    finite = list(filter(lambda x: x.name == plant_name,
                         grid.children))[0]

    for market in grid.past_markets:
        trades_sold = []
        for trade in market.trades:
            assert trade.buyer is not finite.name
            if trade.seller == finite.name:
                trades_sold.append(trade)
        assert sum([trade.offer.energy for trade in trades_sold]) <= \
            convert_kW_to_kWh(finite.strategy.max_available_power_kW[market.time_slot],
                              finite.config.slot_length)


@then("the results are the same for each simulation run")
def test_sim_market_count(context):
    if GlobalConfig.IS_CANARY_NETWORK:
        return
    grid_1 = context.simulation_1.area
    grid_4 = context.simulation_4.area
    for market_1 in grid_1.past_markets:
        market_4 = grid_4.get_past_market(market_1.time_slot)
        for area in market_1.traded_energy.keys():
            assert isclose(market_1.traded_energy[area], market_4.traded_energy[area])


@then("we test the config parameters")
def test_config_parameters(context):
    grid = context.simulation.area
    assert all([rate == 35 for rate in grid.config.market_maker_rate.values()])
    assert grid.config.cloud_coverage == 1


def _filter_markets_by_market_name(context, market_name):
    grid = context.simulation.area
    neigh1 = list(filter(lambda x: x.name == "Neighborhood 1", grid.children))[0]
    neigh2 = list(filter(lambda x: x.name == "Neighborhood 2", grid.children))[0]
    if market_name == "Grid":
        return grid.past_markets
    elif market_name in ["Neighborhood 1", "Neighborhood 2"]:
        return (list(filter(lambda x: x.name == market_name, grid.children))[0]).past_markets
    elif market_name == "House 1":
        return (list(filter(lambda x: x.name == market_name, neigh1.children))[0]).past_markets
    elif market_name == "House 2":
        return (list(filter(lambda x: x.name == market_name, neigh2.children))[0]).past_markets


@then('trades on the {market_name} market clear with {trade_rate} cents/kWh and '
      'at grid_fee_rate with {grid_fee_rate} cents/kWh')
def assert_trade_rates(context, market_name, trade_rate, grid_fee_rate=0):
    markets = _filter_markets_by_market_name(context, market_name)

    assert any(len(market.trades) > 0 for market in markets)
    for market in markets:
        for t in market.trades:
            assert isclose(t.offer.price / t.offer.energy, float(trade_rate))
            assert isclose(t.fee_price / t.offer.energy, float(grid_fee_rate), rel_tol=1e-05)


@then('trades on {market_name} clear with {house_1_rate} or {house_2_rate} cents/kWh')
def assert_trade_rates_bottom_to_top(context, market_name, house_1_rate, house_2_rate):
    markets = _filter_markets_by_market_name(context, market_name)
    for market in markets:
        for t in market.trades:
            assert isclose(t.offer.price / t.offer.energy, float(house_1_rate)) or \
                   isclose(t.offer.price / t.offer.energy, float(house_2_rate))


@then('trades on the {market_name} market clear using a rate of either {trade_rate1} or '
      '{trade_rate2} cents/kWh')
def assert_multiple_trade_rates_any(context, market_name, trade_rate1, trade_rate2):
    markets = _filter_markets_by_market_name(context, market_name)
    for market in markets:
        for t in market.trades:
            assert isclose(t.offer.price / t.offer.energy, float(trade_rate1)) or \
                   isclose(t.offer.price / t.offer.energy, float(trade_rate2))


@then('the unmatched loads are identical no matter if the past markets are kept')
def identical_unmatched_loads(context):
    raw_results = context.simulation.endpoint_buffer.results_handler.all_raw_results
    assert len(DeepDiff(raw_results["unmatched_loads"], context.unmatched_loads)) == 0


@then('the cumulative grid trades are identical no matter if the past markets are kept')
def identical_cumulative_grid_trades(context):
    raw_results = context.simulation.endpoint_buffer.results_handler.all_raw_results
    assert len(DeepDiff(raw_results["cumulative_grid_trades"], context.cumulative_grid_trades,
                        significant_digits=5)) == 0


@then('the price energy day results are identical no matter if the past markets are kept')
def identical_price_energy_day(context):
    raw_results = context.simulation.endpoint_buffer.results_handler.all_raw_results
    assert len(DeepDiff(raw_results["price_energy_day"], context.price_energy_day)) == 0


@then('the energy bills are identical no matter if the past markets are kept')
def identical_energy_bills(context):
    raw_results = context.simulation.endpoint_buffer.results_handler.all_raw_results
    ui_results = context.simulation.endpoint_buffer.results_handler.all_ui_results
    energy_bills = raw_results["bills"]
    energy_bills_redis = ui_results["bills"]

    assert len(DeepDiff(energy_bills, context.energy_bills)) == 0
    for _, v in energy_bills_redis.items():
        assert any(len(DeepDiff(v, old_area_results)) == 0
                   for _, old_area_results in context.energy_bills_redis.items())


@then('the cumulative bills are identical no matter if the past markets are kept')
def identical_cumulative_bills(context):
    raw_results = context.simulation.endpoint_buffer.results_handler.all_raw_results
    energy_bills = raw_results["cumulative_bills"]

    for _, v in energy_bills.items():
        assert any(len(DeepDiff(v, old_area_results)) == 0
                   for _, old_area_results in context.energy_bills.items())


@then("the load profile should be identical on each day")
def identical_profiles(context):
    raw_results = context.simulation.endpoint_buffer.results_handler.all_raw_results
    device_stats_dict = raw_results["device_statistics"]
    load_profile = device_stats_dict['House 1']['H1 DefinedLoad']['load_profile_kWh']
    load_profile_ts = {int(from_format(time_slot, DATE_TIME_FORMAT).timestamp()): value
                       for time_slot, value in load_profile.items()}
    start = int(list(load_profile_ts.keys())[0])
    end = int(list(load_profile_ts.keys())[23])
    assert all([load_profile_ts[i] == load_profile_ts[i + 86400] for i in range(start, end, 3600)])


@then("the PV initial selling rate subtracts grid fees")
def pv_selling_rate_minus_fees(context):
    grid = context.simulation.area
    hood2 = list(filter(lambda x: x.name == "Neighborhood 2", context.simulation.area.children))[0]
    house2 = list(filter(lambda x: x.name == "House 2", hood2.children))[0]
    pv = list(filter(lambda x: x.name == "H2 PV", house2.children))[0]

    market_maker_rate = 30
    fees_path_to_root = grid.grid_fee_constant + hood2.grid_fee_constant + house2.grid_fee_constant
    trades_sold = []
    for market in grid.past_markets:
        for trade in market.trades:
            assert trade.buyer is not pv.name
            trade.offer.next_market = market
            if trade.seller == pv.name:
                trades_sold.append(trade)

    assert all([isclose(trade.offer.price / trade.offer.energy,
                        market_maker_rate - fees_path_to_root)
                for trade in trades_sold])


@then("the load initial buying rate adds grid fees")
def load_buying_rate_plus_fees(context):
    grid = context.simulation.area
    hood1 = list(filter(lambda x: x.name == "Neighborhood 1", context.simulation.area.children))[0]
    house1 = list(filter(lambda x: x.name == "House 1", hood1.children))[0]
    load = list(filter(lambda x: x.name == "H1 General Load", house1.children))[0]

    market_maker_rate = 30
    fees_path_to_root = grid.grid_fee_constant + hood1.grid_fee_constant + house1.grid_fee_constant
    trades_bought = []
    for market in grid.past_markets:
        for trade in market.trades:
            assert trade.seller is not load.name
            trade.offer.next_market = market
            if trade.buyer == load.name:
                trades_bought.append(trade)

    assert all([isclose(trade.offer.price / trade.offer.energy,
                        market_maker_rate + fees_path_to_root)
                for trade in trades_bought])


def get_simulation_raw_results(context):
    area_tree_summary = glob.glob(os.path.join(context.export_path, "*", "area_tree_summary.json"))
    with open(area_tree_summary[0], "r") as sf:
        context.area_tree_summary_data = json.load(sf)
    context.name_uuid_map = get_area_name_uuid_mapping(context.area_tree_summary_data)

    raw_data_dir_path = glob.glob(os.path.join(context.export_path, "*", "raw_data", "*"))
    context.raw_sim_data = {}
    for raw in raw_data_dir_path:
        time = raw.split("/")[-1].split('.')[0]
        with open(raw, "r") as sf:
            parsed_raw_data = json.load(sf)
            context.raw_sim_data[time] = parsed_raw_data
