import uuid

import d3a.constants
from behave import given, then
from d3a.d3a_core.util import d3a_path
from d3a.models.config import SimulationConfig
from d3a_interface.constants_limits import GlobalConfig
from d3a_interface.read_user_profile import read_arbitrary_profile, InputProfileTypes
from pendulum import duration


@given("uuids are initiated")
def init_uuids(context):
    context.config_uuid = str(uuid.uuid4())
    context.pv_area_uuid = str(uuid.uuid4())
    context.pv_profile_uuid = str(uuid.uuid4())
    context.load_area_uuid = str(uuid.uuid4())
    context.load_profile_uuid = str(uuid.uuid4())
    GlobalConfig.slot_length = duration(minutes=60)


@given("a yearly PV profile exist in the DB")
def pv_yearly_profile(context):
    from integration_tests.write_user_profiles import write_yearly_user_profiles_to_db
    context.daily_profile_pv = \
        read_arbitrary_profile(InputProfileTypes.POWER,
                               d3a_path + '/resources/Solar_Curve_W_sunny.csv')

    write_yearly_user_profiles_to_db(context.daily_profile_pv,
                                     InputProfileTypes.POWER.value,
                                     context.config_uuid,
                                     context.pv_area_uuid,
                                     context.pv_profile_uuid)


@given("a yearly Load profile exist in the DB")
def load_yearly_profile(context):
    from integration_tests.write_user_profiles import write_yearly_user_profiles_to_db
    context.daily_profile_load = \
        read_arbitrary_profile(InputProfileTypes.POWER,
                               d3a_path + '/resources/LOAD_DATA_1.csv')
    write_yearly_user_profiles_to_db(context.daily_profile_load,
                                     InputProfileTypes.POWER.value,
                                     context.config_uuid,
                                     context.load_area_uuid,
                                     context.load_profile_uuid)


@given("the connection to the profiles DB is disconnected")
def disconnect_from_profiles_db(context):
    from integration_tests.environment import profiles_handler
    profiles_handler.disconnect()


@given("a configuration containing a PV and Load using profile_uuids exists")
def db_profile_scenario(context):
    predefined_load_scenario = {
        "name": "Grid",
        "children": [
            {
                "name": "Market Maker",
                "type": "MarketMaker",
                "energy_rate": 30
            },
            {
                "name": "House",
                "children": [
                    {
                        "name": "Load",
                        "uuid": context.load_area_uuid,
                        "type": "LoadProfile",
                        "daily_load_profile_uuid": context.load_profile_uuid
                    },
                    {
                        "name": "PV",
                        "uuid": context.pv_area_uuid,
                        "type": "PVProfile",
                        "power_profile_uuid": context.pv_profile_uuid
                    }
                ]
            },
        ]
    }
    context._settings = SimulationConfig(sim_duration=duration(days=3),
                                         tick_length=duration(seconds=60),
                                         slot_length=GlobalConfig.slot_length,
                                         market_count=1,
                                         cloud_coverage=0,
                                         external_connection_enabled=False)
    context._settings.area = predefined_load_scenario
    d3a.constants.CONFIGURATION_ID = context.config_uuid


@then('the predefined PV follows the profile from DB')
def check_pv_profile(context):
    house1 = list(filter(lambda x: x.name == "House", context.simulation.area.children))[0]
    pv = list(filter(lambda x: x.name == "PV", house1.children))[0]
    from d3a_interface.utils import convert_W_to_kWh

    daily_energy_profile = [convert_W_to_kWh(power, GlobalConfig.slot_length)
                            for power in context.daily_profile_pv.values()]
    expected_produced_energy = []
    for days in range(GlobalConfig.sim_duration.days):
        expected_produced_energy += daily_energy_profile

    produced_energy = list(pv.strategy.state._energy_production_forecast_kWh.values())
    assert expected_produced_energy == produced_energy


@then('the predefined Load follows the profile from DB')
def check_load_profile(context):
    house1 = list(filter(lambda x: x.name == "House", context.simulation.area.children))[0]
    load = list(filter(lambda x: x.name == "Load", house1.children))[0]

    daily_energy_profile = context.daily_profile_load.values()

    expected_produced_energy = []
    for days in range(GlobalConfig.sim_duration.days):
        expected_produced_energy += daily_energy_profile

    produced_energy = list(load.strategy.state._desired_energy_Wh.values())
    assert expected_produced_energy == produced_energy
