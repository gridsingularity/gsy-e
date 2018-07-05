import os
import importlib
import logging
import glob
from math import isclose
from pendulum.interval import Interval
from behave import given, when, then

from d3a.models.config import SimulationConfig
from d3a.simulation import Simulation
from d3a.models.strategy.predefined_pv import d3a_path


@given('we have a scenario named {scenario}')
def scenario_check(context, scenario):
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


@given('a load profile csv as input to predefined load')
def load_csv_profile(context):
    context._device_profile = os.path.join(d3a_path, 'resources', 'LOAD_DATA_1.csv')


@given('a PV profile csv as input to predefined PV')
def pv_csv_profile(context):
    context._device_profile = os.path.join(d3a_path, 'resources', 'Solar_Curve_W_cloudy.csv')


@given('the scenario includes a predefined load that will not be unmatched')
def load_profile_scenario(context):
    predefined_load_scenario = {
      "name": "Grid",
      "children": [
        {
          "name": "Commercial Energy Producer",
          "type": "CommercialProducer",
          "energy_price": 15.5,
          "energy_range_wh": [40, 120]
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
              "panel_count": 3,
              "risk": 80
            }
          ]
        },
        {
          "name": "House 2",
          "children": [
            {
              "name": "H2 Storage",
              "type": "Storage",
              "capacity": 5,
              "initial_charge": 40
            },
            {
              "name": "H2 Fridge 1",
              "type": "Fridge"
            },
          ]
        }
      ]
    }
    context._settings = SimulationConfig(tick_length=Interval(seconds=15),
                                         slot_length=Interval(minutes=15),
                                         duration=Interval(hours=24),
                                         market_count=4,
                                         cloud_coverage=0,
                                         market_maker_rate=30,
                                         iaa_fee=5)
    context._settings.area = predefined_load_scenario


@given('the scenario includes a predefined PV')
def pv_profile_scenario(context):
    predefined_pv_scenario = {
        "name": "Grid",
        "children": [
            {
                "name": "Commercial Energy Producer",
                "type": "CommercialProducer",
                "energy_price": 15.5,
                "energy_range_wh": [40, 120]
            },
            {
                "name": "House 1",
                "children": [
                    {
                        "name": "H1 Load",
                        "type": "PermanentLoad",
                        "energy": 100
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
                        "capacity": 5,
                        "initial_charge": 40
                    },
                    {
                        "name": "H2 Fridge 1",
                        "type": "Fridge"
                    },
                ]
            }
        ]
    }
    context._settings = SimulationConfig(tick_length=Interval(seconds=15),
                                         slot_length=Interval(minutes=15),
                                         duration=Interval(hours=24),
                                         market_count=4,
                                         cloud_coverage=0,
                                         market_maker_rate=30,
                                         iaa_fee=5)
    context._settings.area = predefined_pv_scenario


@when('the simulation is running')
def running_the_simulation(context):

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.CRITICAL)

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
    context.simulation = Simulation(
        'json_arg',
        context._settings,
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
    context.simulation.run()


@when('we run the d3a simulation on console with {scenario}')
def run_sim_console(context, scenario):
    context.export_path = os.path.join(context.simdir, scenario)
    os.makedirs(context.export_path, exist_ok=True)
    os.system("d3a -l FATAL run -d 2h --setup={scenario} --export --export-path={export_path} "
              "--exit-on-finish".format(export_path=context.export_path, scenario=scenario))


@when('we run simulation on console with default settings file')
def run_d3a_with_settings_file(context):
    context.export_path = os.path.join(context.simdir, "default")
    os.makedirs(context.export_path, exist_ok=True)
    os.system("d3a -l FATAL run -g {settings_file} --export --export-path={export_path} "
              "--exit-on-finish".format(export_path=context.export_path,
                                        settings_file=os.path.join(
                                            d3a_path, "setup", "d3a-settings.json")))


@then('we test the export functionality of {scenario}')
def test_export_data_csv(context, scenario):
    data_fn = "grid.csv"
    sim_data_csv = glob.glob(os.path.join(context.export_path, "*", data_fn))
    if len(sim_data_csv) != 1:
        raise FileExistsError("Not found in {path}: {file} ".format(path=context.export_path,
                                                                    file=data_fn))


@when('a simulation is created for scenario {scenario}')
def create_sim_object(context, scenario):
    simulation_config = SimulationConfig(Interval(hours=int(24)),
                                         Interval(minutes=int(15)),
                                         Interval(seconds=int(30)),
                                         market_count=5,
                                         cloud_coverage=0,
                                         market_maker_rate=30,
                                         iaa_fee=5)

    context.simulation = Simulation(
        scenario, simulation_config, 0, 0, False, Interval(), False, False, None, False,
        Interval(), True, Interval(), None, "1234"
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
    root_logger.setLevel(logging.CRITICAL)
    context.simulation.run()


@when('a message is sent on {channel}')
def message_on_channel(context, channel):
    context.simulation.redis_connection._sub_callback_dict[channel](None)


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


@then('intermediate results are transmitted on every slot')
def interm_res_report(context):
    assert context.interm_results_count == 97


@then('final results are transmitted once')
def final_res_report(context):
    assert context.final_results_count == 1


@then('{method} is called')
def method_called(context, method):
    assert context.ctrl_callback_call_count == 1


@when('we run the d3a simulation with {scenario} [{duration}, {slot_length}, {tick_length}]')
def run_sim(context, scenario, duration, slot_length, tick_length):

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.CRITICAL)

    simulation_config = SimulationConfig(Interval(hours=int(duration)),
                                         Interval(minutes=int(slot_length)),
                                         Interval(seconds=int(tick_length)),
                                         market_count=5,
                                         cloud_coverage=0,
                                         market_maker_rate=30,
                                         iaa_fee=5)

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
    context.simulation = Simulation(
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
    context.simulation.run()


@then('we test the output of the simulation of '
      '{scenario} [{duration}, {slot_length}, {tick_length}]')
def test_output(context, scenario, duration, slot_length, tick_length):

    # Check if simulation ran through
    # (check if number of last slot is the maximal number of slots):
    no_of_slots = (int(duration) * 60 / int(slot_length)) + 1
    assert no_of_slots == context.simulation.area.current_slot
    # TODO: Implement more sophisticated tests for success of simulation


@then('the predefined load follows the load profile')
def check_load_profile(context):
    house1 = list(filter(lambda x: x.name == "House 1", context.simulation.area.children))[0]
    load = list(filter(lambda x: x.name == "H1 Load", house1.children))[0]
    for timepoint, energy in load.strategy.state.desired_energy.items():
        if timepoint.hour in context._device_profile:
            assert energy == context._device_profile[timepoint.hour] / \
                   (Interval(hours=1) / load.config.slot_length)
        else:
            assert energy == 0


@then('the predefined PV follows the PV profile')
def check_pv_profile(context):
    house1 = list(filter(lambda x: x.name == "House 1", context.simulation.area.children))[0]
    pv = list(filter(lambda x: x.name == "H1 PV", house1.children))[0]
    for timepoint, energy in pv.strategy.energy_production_forecast_kWh.items():
        if timepoint.hour in context._device_profile:
            assert energy == context._device_profile[timepoint.hour] / \
                   (Interval(hours=1) / pv.config.slot_length) / 1000.0
        else:
            assert energy == 0


@then('the predefined load follows the load profile from the csv')
def check_load_profile_csv(context):
    house1 = list(filter(lambda x: x.name == "House 1", context.simulation.area.children))[0]
    load = list(filter(lambda x: x.name == "H1 Load", house1.children))[0]
    input_profile = load.strategy._readCSV(context._device_profile)
    desired_energy = {f'{k.hour:02}:{k.minute:02}': v
                      for k, v in load.strategy.state.desired_energy.items()
                      }

    for timepoint, energy in desired_energy.items():
        if timepoint in input_profile:
            assert energy == input_profile[timepoint] / \
                   (Interval(hours=1) / load.config.slot_length)
        else:
            assert False


@then('the predefined PV follows the PV profile from the csv')
def check_pv_profile_csv(context):
    house1 = list(filter(lambda x: x.name == "House 1", context.simulation.area.children))[0]
    pv = list(filter(lambda x: x.name == "H1 PV", house1.children))[0]
    input_profile = pv.strategy._readCSV(context._device_profile)
    produced_energy = {f'{k.hour:02}:{k.minute:02}': v
                       for k, v in pv.strategy.energy_production_forecast_kWh.items()
                       }
    for timepoint, energy in produced_energy.items():
        if timepoint in input_profile:
            assert energy == input_profile[timepoint] / \
                   (Interval(hours=1) / pv.config.slot_length) / 1000.0
        else:
            assert False


@then('the storage devices buy and sell energy respecting the break even prices')
def check_storage_prices(context):
    house1 = list(filter(lambda x: x.name == "House 1", context.simulation.area.children))[0]
    trades_sold = []
    trades_bought = []
    for slot, market in house1.past_markets.items():
        for trade in market.trades:
            if trade.seller in ["H1 Storage1", "H1 Storage2"]:
                trades_sold.append(trade)
            elif trade.buyer in ["H1 Storage1", "H1 Storage2"]:
                trades_bought.append(trade)
    assert all([trade.offer.price / trade.offer.energy >= 27.01 for trade in trades_sold])
    assert all([trade.offer.price / trade.offer.energy <= 26.99 for trade in trades_bought])
    assert len(trades_sold) > 0
    assert len(trades_bought) > 0


@then('the {plant_name} always sells energy at the defined energy rate')
def test_finite_plant_energy_rate(context, plant_name):
    grid = context.simulation.area
    finite = list(filter(lambda x: x.name == plant_name,
                         context.simulation.area.children))[0]
    trades_sold = []
    for slot, market in grid.past_markets.items():
        for trade in market.trades:
            assert trade.buyer is not finite.name
            if trade.seller == finite.name:
                trades_sold.append(trade)
        assert all([isclose(trade.offer.price / trade.offer.energy, finite.strategy.energy_rate)
                    for trade in trades_sold])
        assert len(trades_sold) > 0


@then('the {plant_name} never produces more power than its max available power')
def test_finite_plant_max_power(context, plant_name):
    grid = context.simulation.area
    finite = list(filter(lambda x: x.name == plant_name,
                         grid.children))[0]

    for slot, market in grid.past_markets.items():
        trades_sold = []
        for trade in market.trades:
            assert trade.buyer is not finite.name
            if trade.seller == finite.name:
                trades_sold.append(trade)
        assert sum([trade.offer.energy for trade in trades_sold]) <= \
            finite.strategy.max_available_power[market.time_slot.hour] / \
            (Interval(hours=1) / finite.config.slot_length)
