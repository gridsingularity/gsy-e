import uuid

import gsy_e.constants
from behave import given, then
from gsy_e.gsy_e_core.util import d3a_path
from gsy_e.models.config import SimulationConfig
from gsy_framework.constants_limits import GlobalConfig
from gsy_framework.read_user_profile import read_arbitrary_profile, InputProfileTypes
from gsy_framework.utils import convert_W_to_kWh
from pendulum import duration


@given("uuids are initiated")
def init_uuids(context):
    context.config_uuid = str(uuid.uuid4())
    context.pv_area_uuid = str(uuid.uuid4())
    context.pv_profile_uuid = str(uuid.uuid4())
    context.load_area_uuid = str(uuid.uuid4())
    context.load_profile_uuid = str(uuid.uuid4())
    context.smart_meter_area_uuid = str(uuid.uuid4())
    context.smart_meter_profile_uuid = str(uuid.uuid4())
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
                               d3a_path + "/resources/LOAD_DATA_1.csv")
    write_yearly_user_profiles_to_db(context.daily_profile_load,
                                     InputProfileTypes.POWER.value,
                                     context.config_uuid,
                                     context.load_area_uuid,
                                     context.load_profile_uuid)


@given("a yearly Smart Meter profile exist in the DB")
def smart_meter_yearly_profile(context):
    from integration_tests.write_user_profiles import write_yearly_user_profiles_to_db
    context.daily_profile_smart_meter = \
        read_arbitrary_profile(InputProfileTypes.POWER,
                               d3a_path + "/resources/smart_meter_profile.csv")
    write_yearly_user_profiles_to_db(context.daily_profile_smart_meter,
                                     InputProfileTypes.POWER.value,
                                     context.config_uuid,
                                     context.smart_meter_area_uuid,
                                     context.smart_meter_profile_uuid)


@given("the connection to the profiles DB is disconnected")
def disconnect_from_profiles_db(context):
    from integration_tests.environment import profiles_handler
    profiles_handler.disconnect()


@given("a configuration with assets using profile_uuids exists")
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
                    },
                    {
                        "name": "Smart Meter",
                        "uuid": context.smart_meter_area_uuid,
                        "type": "SmartMeter",
                        "smart_meter_profile_uuid": context.smart_meter_profile_uuid
                    }
                ]
            },
        ]
    }
    context._settings = SimulationConfig(sim_duration=duration(days=3),
                                         tick_length=duration(seconds=60),
                                         slot_length=GlobalConfig.slot_length,
                                         cloud_coverage=0,
                                         external_connection_enabled=False)
    context._settings.area = predefined_load_scenario
    gsy_e.constants.CONFIGURATION_ID = context.config_uuid


@then('the predefined PV follows the profile from DB')
def check_pv_profile(context):
    house1 = list(filter(lambda x: x.name == "House", context.simulation.area.children))[0]
    pv = list(filter(lambda x: x.name == "PV", house1.children))[0]

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

    expected_consumed_energy = []
    for days in range(GlobalConfig.sim_duration.days):
        expected_consumed_energy += daily_energy_profile

    consumed_energy = list(load.strategy.state._desired_energy_Wh.values())
    assert expected_consumed_energy == consumed_energy


@then('the Smart Meter follows the profile from DB')
def check_smart_meter_profile(context):
    house1 = list(filter(lambda x: x.name == "House", context.simulation.area.children))[0]
    smart_meter = list(filter(lambda x: x.name == "Smart Meter", house1.children))[0]

    daily_energy_profile = context.daily_profile_smart_meter.values()

    expected_energy_profile = []
    for days in range(GlobalConfig.sim_duration.days):
        expected_energy_profile += daily_energy_profile

    consumed_energy_Wh = list(smart_meter.strategy.state._desired_energy_Wh.values())
    produced_energy_kWh = list(smart_meter.strategy.state._energy_production_forecast_kWh.values())
    energy_profile = \
        [consumed - produced_energy_kWh[ii]*1000 for ii, consumed in enumerate(consumed_energy_Wh)]
    assert expected_energy_profile == energy_profile
