"""
Copyright 2018 Grid Singularity
This file is part of Grid Singularity Exchange.

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

import json
from datetime import datetime

import pytest
from gsy_framework.constants_limits import ConstSettings, GlobalConfig
from gsy_framework.enums import GridIntegrationType
from pendulum import datetime as pendulum_datetime, duration, instance

from gsy_e.gsy_e_core.area_serializer import are_all_areas_unique, area_from_string, area_to_string
from gsy_e.models.area import Area
from gsy_e.models.config import SimulationConfig
from gsy_e.models.leaves import (
    PV,
    EVCharger,
    LoadHours,
    SmartMeter,
    Storage,
)
from gsy_e.models.strategy.external_strategies.load import LoadHoursExternalStrategy
from gsy_e.models.strategy.external_strategies.pv import PVExternalStrategy
from gsy_e.models.strategy.external_strategies.storage import StorageExternalStrategy
from gsy_e.models.strategy.pv import PVStrategy
from gsy_e.models.strategy.state.evcharger_state import EVChargingSession
from gsy_e.models.strategy.smart_meter import SmartMeterStrategy
from gsy_e.models.strategy.forward.pv import ForwardPVStrategy
from gsy_e.models.strategy.forward.load import ForwardLoadStrategy


# pylint: disable=protected-access


@pytest.fixture(scope="function", autouse=True)
def _device_registry_auto_fixture():
    yield
    ConstSettings.MASettings.MARKET_TYPE = 1


def _create_config(settings=None):
    if not settings:
        settings = {}
    config_settings = {
        "start_date": (
            instance(datetime.combine(settings.get("start_date"), datetime.min.time()))
            if "start_date" in settings
            else GlobalConfig.start_date
        ),
        "sim_duration": (
            duration(days=settings["duration"].days)
            if "duration" in settings
            else GlobalConfig.sim_duration
        ),
        "slot_length": (
            duration(seconds=settings["slot_length"].seconds)
            if "slot_length" in settings
            else GlobalConfig.slot_length
        ),
        "tick_length": (
            duration(seconds=settings["tick_length"].seconds)
            if "tick_length" in settings
            else GlobalConfig.tick_length
        ),
        "market_maker_rate": settings.get(
            "market_maker_rate", ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE
        ),
        "capacity_kW": settings.get("capacity_kW", ConstSettings.PVSettings.DEFAULT_CAPACITY_KW),
        "grid_fee_type": settings.get("grid_fee_type", GlobalConfig.grid_fee_type),
        "external_connection_enabled": settings.get("external_connection_enabled", False),
        "aggregator_device_mapping": None,
    }
    return SimulationConfig(**config_settings)


def test_area_with_children_roundtrip():
    child1 = Area("child1")
    child2 = Area("child2")
    parent = Area("parent", [child1, child2])
    string = area_to_string(parent)
    recovered = area_from_string(string, _create_config())
    assert recovered.name == "parent"
    assert recovered.children[0].name == "child1"
    assert recovered.children[1].name == "child2"


def test_raises_unknown_class():
    with pytest.raises(ValueError):
        area_from_string("{'name':'broken','strategy':'NonexistentStrategy'}", _create_config())


def test_strategy_roundtrip_with_params():
    area = Area("area", [], None, PVStrategy(panel_count=42))
    area_str = area_to_string(area)
    recovered = area_from_string(area_str, _create_config())
    assert recovered.strategy._energy_params.panel_count == 42


def test_non_attr_param():
    area1 = Area("area1", [], None, PVStrategy())
    recovered1 = area_from_string(area_to_string(area1), _create_config())
    assert recovered1.strategy._energy_params.capacity_kW is None
    assert (
        recovered1.strategy.offer_update.final_rate_profile_buffer.get_value(
            area1.config.start_date
        )
        == ConstSettings.PVSettings.SELLING_RATE_RANGE.final
    )


def test_leaf_deserialization():
    recovered = area_from_string(
        """{
             "name": "house",
             "children":[
                 {"name": "pv1", "type": "PV", "panel_count": 4, "display_type": "PV"},
                 {"name": "pv2", "type": "PV", "panel_count": 1, "display_type": "PV"},
                 {"name": "smart meter", "type": "SmartMeter",
                  "smart_meter_profile": "some_path.csv"}
             ]
           }
        """,
        config=_create_config(),
    )
    pv1, pv2, smart_meter = recovered.children
    assert isinstance(pv1, PV)
    assert pv1.strategy._energy_params.panel_count == 4
    assert pv1.display_type == "PV"
    assert isinstance(pv2, PV)
    assert pv2.strategy._energy_params.panel_count == 1
    assert pv2.display_type == "PV"
    assert isinstance(smart_meter, SmartMeter)


def test_leaf_external_connection_deserialization():
    recovered = area_from_string(
        """{
             "name": "house",
             "children":[
                 {"name": "pv1", "type": "PV", "panel_count": 4, "display_type": "PV",
                 "allow_external_connection": true},
                 {"name": "load1", "type": "LoadHours", "avg_power_W": 200, "display_type": "Load",
                 "allow_external_connection": true},
                 {"name": "storage1", "type": "Storage", "display_type": "Storage",
                 "allow_external_connection": true}
             ]
           }
        """,
        _create_config({"external_connection_enabled": True}),
    )

    pv1, load1, storage1 = recovered.children
    assert isinstance(pv1, PV)
    assert isinstance(pv1.strategy, PVExternalStrategy)
    assert pv1.strategy._energy_params.panel_count == 4
    assert pv1.display_type == "PV"
    assert isinstance(load1, LoadHours)
    assert isinstance(load1.strategy, LoadHoursExternalStrategy)
    assert load1.strategy._energy_params.avg_power_W == 200
    assert load1.display_type == "Load"
    assert isinstance(storage1, Storage)
    assert isinstance(storage1.strategy, StorageExternalStrategy)
    assert storage1.display_type == "Storage"


def test_leaf_deserialization_does_not_deserialize_invalid_args():
    recovered = area_from_string(
        """{
             "name": "house",
             "children":[
                 {"name": "pv1", "type": "PV", "panel_count": 4,
                  "display_type": "PV", "load_profile": "test.csv"},
                 {"name": "load1", "type": "LoadHours", "avg_power_W": 200,
                 "allow_external_connection": true},
                 {"name": "storage1", "type": "Storage", "display_type": "Storage",
                 "allow_external_connection": true}
             ]
           }
        """,
        _create_config(),
    )

    assert isinstance(recovered.children[0], PV)
    assert not hasattr(recovered.children[0].strategy, "load_profile")
    assert recovered.children[0].strategy._energy_params.panel_count == 4


@pytest.fixture
def _fixture_with_leaves():
    area = Area(
        "house",
        [
            PV("pv1", panel_count=1, config=_create_config()),
            PV("pv2", panel_count=4, config=_create_config()),
            SmartMeter(
                "smart meter", smart_meter_profile="some_path.csv", config=_create_config()
            ),
        ],
    )
    return area_to_string(area)


def test_leaf_serialization(_fixture_with_leaves):
    description = json.loads(_fixture_with_leaves)
    assert len(description["children"]) == 3
    assert description["children"][0]["type"] == "PV"
    assert description["children"][0]["panel_count"] == 1
    assert description["children"][1]["type"] == "PV"
    assert description["children"][1]["panel_count"] == 4
    assert description["children"][2]["type"] == "SmartMeter"


def test_roundtrip_with_leaf(_fixture_with_leaves):
    recovered = area_from_string(_fixture_with_leaves, _create_config())
    assert isinstance(recovered.children[0].strategy, PVStrategy)
    assert isinstance(recovered.children[1].strategy, PVStrategy)
    assert isinstance(recovered.children[2].strategy, SmartMeterStrategy)


def test_ev_charger_leaf_deserialization():
    recovered = area_from_string(
        """{
             "name": "house",
             "children":[
                 {"name": "ev charger", "type": "EVCharger", "display_type": "EVCharger",
                  "grid_integration": 1, "maximum_power_rating_kW": 22,
                  "preferred_charging_power": 11, "charging_efficiency": null,
                  "charging_sessions": [
                      {"plug_in_time": "2024-01-30T08:00", "duration_minutes": 60,
                       "initial_soc_percent": 20, "min_soc_percent": 80,
                       "battery_capacity_kWh": 60},
                      {"plug_in_time": "2024-01-30T18:00", "duration_minutes": 90,
                       "initial_soc_percent": null, "min_soc_percent": null,
                       "battery_capacity_kWh": null}
                  ]}
             ]
           }
        """,
        _create_config(),
    )

    ev_charger = recovered.children[0]
    assert isinstance(ev_charger, EVCharger)
    assert ev_charger.display_type == "EVCharger"
    strategy = ev_charger.strategy
    assert strategy.grid_integration == GridIntegrationType.BIDIRECTIONAL
    assert strategy.maximum_power_rating_kW == 22
    assert strategy.preferred_charging_power == 11
    configured_session, default_session = strategy.charging_sessions
    assert isinstance(configured_session, EVChargingSession)
    assert configured_session.plug_in_time == pendulum_datetime(2024, 1, 30, 8)
    assert configured_session.duration_minutes == 60
    assert configured_session.initial_soc_percent == 20
    assert configured_session.min_soc_percent == 80
    assert configured_session.battery_capacity_kWh == 60
    assert default_session.plug_in_time == pendulum_datetime(2024, 1, 30, 18)
    assert default_session.initial_soc_percent == 20.0
    assert default_session.min_soc_percent == 50.0
    assert default_session.battery_capacity_kWh == 100.0


def test_ev_charger_roundtrip_keeps_charging_sessions():
    area = Area(
        "house",
        [
            EVCharger(
                "ev charger",
                grid_integration=GridIntegrationType.UNIDIRECTIONAL,
                maximum_power_rating_kW=11,
                preferred_charging_power=5,
                charging_efficiency=0.8,
                charging_sessions=[
                    EVChargingSession(
                        plug_in_time=pendulum_datetime(2024, 1, 30, 8),
                        duration_minutes=60,
                        initial_soc_percent=30,
                        min_soc_percent=70,
                        battery_capacity_kWh=40,
                    )
                ],
                config=_create_config(),
            )
        ],
    )

    recovered = area_from_string(area_to_string(area), _create_config())

    assert (
        not {
            "initial_soc",
            "min_allowed_soc",
            "battery_capacity_kWh",
            "max_abs_battery_power_kW",
        }
        & area.children[0].parameters.keys()
    )
    strategy = recovered.children[0].strategy
    assert strategy.grid_integration == GridIntegrationType.UNIDIRECTIONAL
    assert strategy.maximum_power_rating_kW == 11
    assert strategy.preferred_charging_power == 5
    assert strategy.charging_efficiency == 0.8
    [session] = strategy.charging_sessions
    assert session.plug_in_time == pendulum_datetime(2024, 1, 30, 8)
    assert session.duration_minutes == 60
    assert session.initial_soc_percent == 30
    assert session.min_soc_percent == 70
    assert session.battery_capacity_kWh == 40


def test_ev_charger_normalises_int_grid_integration():
    area = Area("house", [EVCharger("ev charger", grid_integration=0, config=_create_config())])

    serialized = area_to_string(area)

    assert area.children[0].strategy.grid_integration is GridIntegrationType.UNIDIRECTIONAL
    assert '"grid_integration": 0' in serialized


def test_area_does_not_allow_duplicate_subarea_names():
    area = Area(
        "Grid",
        [
            Area("House 1", children=[Area("H1 General Load"), Area("H1 PV1")]),
            Area("House 1", children=[Area("H2 General Load"), Area("H2 PV1")]),
        ],
    )

    with pytest.raises(AssertionError):
        are_all_areas_unique(area, set())

    area = Area(
        "Grid",
        [
            Area("House 1", children=[Area("H1 General Load"), Area("H1 PV1")]),
            Area("House 2", children=[Area("H1 General Load"), Area("H2 PV1")]),
        ],
    )

    with pytest.raises(AssertionError):
        are_all_areas_unique(area, set())

    area = Area(
        "Grid",
        [
            Area("House 1", children=[Area("H1 General Load"), Area("H1 PV1")]),
            Area("House 2", children=[Area("H2 General Load"), Area("H2 PV1")]),
        ],
    )

    # Does not raise an assertion
    are_all_areas_unique(area, set())


@pytest.fixture
def _forward_fixture():
    ConstSettings.ForwardMarketSettings.ENABLE_FORWARD_MARKETS = True
    yield
    ConstSettings.ForwardMarketSettings.ENABLE_FORWARD_MARKETS = False


def test_leaf_deserialization_works_for_forward_strategies(_forward_fixture):
    deserialized_area = area_from_string(
        """
        {
             "name": "house",
             "children": [
                 {"name": "pv1", "type": "PV", "capacity_kW": 1000},
                 {"name": "load1", "type": "LoadHours", "capacity_kW": 2000}
             ]
        }
        """,
        _create_config(),
    )

    assert deserialized_area.children[0].strategy is not None
    assert isinstance(deserialized_area.children[0].strategy, ForwardPVStrategy)
    assert deserialized_area.children[0].strategy._energy_params.capacity_kW == 1000.0

    assert deserialized_area.children[1].strategy is not None
    assert isinstance(deserialized_area.children[1].strategy, ForwardLoadStrategy)
    assert deserialized_area.children[1].strategy._energy_params.capacity_kW == 2000.0
