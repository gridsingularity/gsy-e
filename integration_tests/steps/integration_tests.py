import os
import importlib
import logging
import glob
from math import isclose
from pendulum import duration
from behave import given, when, then

from d3a.models.config import SimulationConfig
from d3a.models.strategy.mixins import ReadProfileMixin
from d3a.simulation import Simulation
from d3a.models.strategy.predefined_pv import d3a_path
from d3a import TIME_FORMAT, PENDULUM_TIME_FORMAT
from d3a.models.strategy.const import ConstSettings
from d3a.export_unmatched_loads import export_unmatched_loads


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


@given('a {device} profile string as input to predefined load')
def json_string_profile(context, device):
    context._device_profile_dict = {i: 100 for i in range(10)}
    context._device_profile_dict.update({i: 50 for i in range(10, 20)})
    context._device_profile_dict.update({i: 25 for i in range(20, 24)})
    profile = "{"
    for i in range(24):
        for j in ["00", "15", "30", "45"]:
            if i < 10:
                profile += f"\"{i:02}:{j}\": 100, "
            elif 10 <= i < 20:
                profile += f"\"{i:02}:{j}\": 50, "
            else:
                profile += f"\"{i:02}:{j}\": 25, "
    profile += "}"
    context._device_profile = profile


@given('we have a profile of market_maker_rate for {scenario}')
def hour_profile_of_market_maker_rate(context, scenario):
    import importlib
    from d3a.models.strategy.mixins import ReadProfileMixin
    from d3a.models.strategy.mixins import InputProfileTypes
    setup_file_module = importlib.import_module("d3a.setup.{}".format(scenario))
    context._market_maker_rate = ReadProfileMixin.\
        read_arbitrary_profile(InputProfileTypes.RATE, setup_file_module.market_maker_rate)
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
    context._settings = SimulationConfig(tick_length=duration(seconds=15),
                                         slot_length=duration(minutes=15),
                                         duration=duration(hours=24),
                                         market_count=4,
                                         cloud_coverage=0,
                                         market_maker_rate=30,
                                         iaa_fee=5)
    context._settings.area = predefined_pv_scenario


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
    context._settings = SimulationConfig(tick_length=duration(seconds=15),
                                         slot_length=duration(minutes=15),
                                         duration=duration(hours=24),
                                         market_count=4,
                                         cloud_coverage=0,
                                         market_maker_rate=30,
                                         iaa_fee=5)
    context._settings.area = predefined_load_scenario


@when('the simulation is running')
def running_the_simulation(context):

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.CRITICAL)

    slowdown = 0
    seed = 0
    paused = False
    pause_after = duration()
    repl = False
    export = False
    export_path = None
    reset_on_finish = False
    reset_on_finish_wait = duration()
    exit_on_finish = True
    exit_on_finish_wait = duration()

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


@when('we run the d3a simulation with config parameters'
      ' [{cloud_coverage}, {iaa_fee}] and {scenario}')
def run_sim_with_config_setting(context, cloud_coverage,
                                iaa_fee, scenario):

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.CRITICAL)

    simulation_config = SimulationConfig(duration(hours=int(24)),
                                         duration(minutes=int(60)),
                                         duration(seconds=int(60)),
                                         market_count=5,
                                         cloud_coverage=int(cloud_coverage),
                                         market_maker_rate=context._market_maker_rate,
                                         iaa_fee=int(iaa_fee))

    slowdown = 0
    seed = 0
    paused = False
    pause_after = duration()
    repl = False
    export = False
    export_path = None
    reset_on_finish = False
    reset_on_finish_wait = duration()
    exit_on_finish = True
    exit_on_finish_wait = duration()

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


@then('we test that config parameters are correctly parsed for {scenario}'
      ' [{cloud_coverage}, {iaa_fee}]')
def test_simulation_config_parameters(context, scenario, cloud_coverage, iaa_fee):
    from d3a.models.strategy.mixins import default_profile_dict
    assert context.simulation.simulation_config.cloud_coverage == int(cloud_coverage)
    assert len(context.simulation.simulation_config.market_maker_rate) == 24 * 60
    assert len(default_profile_dict().keys()) == len(context.simulation.simulation_config.
                                                     market_maker_rate.keys())
    assert context.simulation.simulation_config.market_maker_rate["01:59"] == 0
    assert context.simulation.simulation_config.market_maker_rate["12:00"] == \
        context._market_maker_rate["11:00"]
    assert context.simulation.simulation_config.market_maker_rate["23:00"] == \
        context._market_maker_rate["22:00"]
    assert context.simulation.simulation_config.iaa_fee == int(iaa_fee)


@when('a simulation is created for scenario {scenario}')
def create_sim_object(context, scenario):
    simulation_config = SimulationConfig(duration(hours=int(24)),
                                         duration(minutes=int(15)),
                                         duration(seconds=int(30)),
                                         market_count=5,
                                         cloud_coverage=0,
                                         market_maker_rate=30,
                                         iaa_fee=5)

    context.simulation = Simulation(
        scenario, simulation_config, 0, 0, False, duration(), False, False, None, False,
        duration(), True, duration(), None, "1234"
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
    assert context.interm_results_count == 96


@then('final results are transmitted once')
def final_res_report(context):
    assert context.final_results_count == 1


@then('{method} is called')
def method_called(context, method):
    assert context.ctrl_callback_call_count == 1


@when('we run the d3a simulation with {scenario} [{total_duration}, '
      '{slot_length}, {tick_length}]')
def run_sim_without_iaa_fee(context, scenario, total_duration, slot_length, tick_length):
    run_sim(context, scenario, total_duration, slot_length, tick_length,
            ConstSettings.INTER_AREA_AGENT_FEE_PERCENTAGE)


@when('we run the simulation with setup file {scenario} '
      'and parameters [{total_duration}, {slot_length}, {tick_length}, {iaa_fee}]')
def run_sim(context, scenario, total_duration, slot_length, tick_length, iaa_fee):

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.CRITICAL)

    simulation_config = SimulationConfig(duration(hours=int(total_duration)),
                                         duration(minutes=int(slot_length)),
                                         duration(seconds=int(tick_length)),
                                         market_count=5,
                                         cloud_coverage=0,
                                         market_maker_rate=30,
                                         iaa_fee=int(iaa_fee))

    slowdown = 0
    seed = 0
    paused = False
    pause_after = duration()
    repl = False
    export = False
    export_path = None
    reset_on_finish = False
    reset_on_finish_wait = duration()
    exit_on_finish = True
    exit_on_finish_wait = duration()

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

    if scenario in ["default_2", "default_2a", "default_3"]:
        unmatched = export_unmatched_loads(context.simulation.area)
        assert unmatched["unmatched_load_count"] == 0
    # (check if number of last slot is the maximal number of slots):
    no_of_slots = (int(duration) * 60 / int(slot_length))
    assert no_of_slots == context.simulation.area.current_slot
    if scenario == "default":
        street1 = list(filter(lambda x: x.name == "Street 1", context.simulation.area.children))[0]
        house1 = list(filter(lambda x: x.name == "S1 House 1", street1.children))[0]
        permanent_load = list(filter(lambda x: x.name == "S1 H1 Load", house1.children))[0]
        energy_profile = [ki for ki in permanent_load.strategy.state.desired_energy.values()]
        assert all([permanent_load.strategy.energy == ei for ei in energy_profile])


@then('the predefined load follows the load profile')
def check_load_profile(context):
    if isinstance(context._device_profile, str):
        context._device_profile = context._device_profile_dict

    house1 = list(filter(lambda x: x.name == "House 1", context.simulation.area.children))[0]
    load = list(filter(lambda x: x.name == "H1 Load", house1.children))[0]
    for timepoint, energy in load.strategy.state.desired_energy.items():
        if timepoint.hour in context._device_profile:
            assert energy == context._device_profile[timepoint.hour] / \
                   (duration(hours=1) / load.config.slot_length)
        else:
            assert energy == 0


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
    profile_data = ReadProfileMixin._readCSV(path)
    for timepoint, energy in pv.strategy.energy_production_forecast_kWh.items():
        time = str(timepoint.format(PENDULUM_TIME_FORMAT))
        if time in profile_data.keys():
            assert energy == profile_data[time] / \
                   (duration(hours=1) / pv.config.slot_length) / 1000.0
        else:
            assert energy == 0


@then('the UserProfile PV follows the PV profile as dict')
def check_user_pv_dict_profile(context):
    house1 = list(filter(lambda x: x.name == "House 1", context.simulation.area.children))[0]
    pv = list(filter(lambda x: x.name == "H1 PV", house1.children))[0]
    from d3a.setup.strategy_tests.user_profile_pv_dict import user_profile
    profile_data = user_profile
    for timepoint, energy in pv.strategy.energy_production_forecast_kWh.items():
        if timepoint.hour in profile_data.keys():
            assert energy == profile_data[timepoint.hour] / \
                   (duration(hours=1) / pv.config.slot_length) / 1000.0
        else:
            if int(timepoint.hour) > int(list(user_profile.keys())[-1]):
                assert energy == user_profile[list(user_profile.keys())[-1]] / \
                   (duration(hours=1) / pv.config.slot_length) / 1000.0
            else:
                assert energy == 0


@then('the UserProfile PV follows the PV profile of csv')
def check_pv_csv_profile(context):
    house1 = list(filter(lambda x: x.name == "House 1", context.simulation.area.children))[0]
    pv = list(filter(lambda x: x.name == "H1 PV", house1.children))[0]
    from d3a.setup.strategy_tests.user_profile_pv_csv import user_profile_path
    profile_data = ReadProfileMixin._readCSV(user_profile_path)
    for timepoint, energy in pv.strategy.energy_production_forecast_kWh.items():
        time = str(timepoint.format(PENDULUM_TIME_FORMAT))
        if time in profile_data.keys():
            assert energy == profile_data[time] / \
                   (duration(hours=1) / pv.config.slot_length) / 1000.0
        else:
            assert energy == 0


@then('the predefined PV follows the PV profile from the csv')
def check_pv_profile_csv(context):
    from d3a.models.strategy.mixins import ReadProfileMixin
    house1 = list(filter(lambda x: x.name == "House 1", context.simulation.area.children))[0]
    pv = list(filter(lambda x: x.name == "H1 PV", house1.children))[0]
    input_profile = ReadProfileMixin._readCSV(context._device_profile)
    produced_energy = {f'{k.hour:02}:{k.minute:02}': v
                       for k, v in pv.strategy.energy_production_forecast_kWh.items()
                       }
    for timepoint, energy in produced_energy.items():
        if timepoint in input_profile:
            assert energy == input_profile[timepoint] / \
                   (duration(hours=1) / pv.config.slot_length) / 1000.0
        else:
            assert False


@then('the {plant_name} always sells energy at the defined energy rate')
def test_finite_plant_energy_rate(context, plant_name):
    grid = context.simulation.area
    finite = list(filter(lambda x: x.name == plant_name,
                         grid.children))[0]
    trades_sold = []
    for slot, market in grid.past_markets.items():
        for trade in market.trades:
            assert trade.buyer is not finite.name
            if trade.seller == finite.name:
                trades_sold.append(trade)
        assert all([isclose(trade.offer.price / trade.offer.energy, finite.strategy.energy_rate)
                    for trade in trades_sold])
        assert len(trades_sold) > 0


@then('the {plant_name} always sells energy at the defined market maker rate')
def test_infinite_plant_energy_rate(context, plant_name):
    grid = context.simulation.area
    finite = list(filter(lambda x: x.name == plant_name,
                         grid.children))[0]
    trades_sold = []
    for slot, market in grid.past_markets.items():
        for trade in market.trades:
            assert trade.buyer is not finite.name
            if trade.seller == finite.name:
                trades_sold.append(trade)
        assert all([isclose(trade.offer.price / trade.offer.energy,
                    context.simulation.simulation_config.
                            market_maker_rate[trade.time.strftime(TIME_FORMAT)])
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
            finite.strategy.max_available_power_kW[market.time_slot.hour].m / \
            (duration(hours=1) / finite.config.slot_length)


@then('the PV sells energy at the market maker rate for every market slot')
def test_pv_initial_pv_rate_option(context):
    grid = context.simulation.area
    house = list(filter(lambda x: x.name == "House", grid.children))[0]

    for slot, market in house.past_markets.items():
        for trade in market.trades:
            assert isclose(trade.offer.price / trade.offer.energy,
                           grid.config.market_maker_rate[market.time_slot_str])
