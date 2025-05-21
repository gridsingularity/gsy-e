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
from gsy_framework.constants_limits import ConstSettings, GlobalConfig, SpotMarketTypeEnum
from pendulum import duration, instance

from gsy_e.gsy_e_core.area_serializer import are_all_areas_unique, area_from_string, area_to_string
from gsy_e.models.area import Area
from gsy_e.models.config import SimulationConfig
from gsy_e.models.leaves import (
    PV,
    LoadHours,
    SmartMeter,
    Storage,
    SCMLoadHours,
    SCMLoadProfile,
    SCMPVProfile,
    SCMStorage,
)
from gsy_e.models.strategy.external_strategies.load import LoadHoursExternalStrategy
from gsy_e.models.strategy.external_strategies.pv import PVExternalStrategy
from gsy_e.models.strategy.external_strategies.storage import StorageExternalStrategy
from gsy_e.models.strategy.pv import PVStrategy
from gsy_e.models.strategy.scm.load import SCMLoadHoursStrategy, SCMLoadProfileStrategy
from gsy_e.models.strategy.scm.pv import SCMPVUserProfile
from gsy_e.models.strategy.scm.storage import SCMStorageStrategy
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
        recovered1.strategy.offer_update.final_rate_profile_buffer.profile[area1.config.start_date]
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


def test_leaf_deserialization_scm():
    ConstSettings.MASettings.MARKET_TYPE = SpotMarketTypeEnum.COEFFICIENTS.value
    recovered = area_from_string(
        """{
             "name": "house",
             "children":[
                 {"name": "pv1", "type": "PVProfile", "power_profile": "test1.csv",
                  "power_profile_uuid": "fedcba"},
                 {"name": "load1", "type": "LoadHours", "avg_power_W": 200},
                 {"name": "load1", "type": "LoadProfile", "daily_load_profile": "test.csv",
                  "daily_load_profile_uuid": "abcdef"},
                 {"name": "storage1", "type": "ScmStorage", "initial_soc": 34}
             ]
           }
        """,
        _create_config(),
    )

    assert isinstance(recovered.children[0], SCMPVProfile)
    assert isinstance(recovered.children[0].strategy, SCMPVUserProfile)

    assert (
        recovered.children[0].strategy._energy_params.energy_profile.input_profile == "test1.csv"
    )
    assert recovered.children[0].strategy._energy_params.energy_profile.input_profile_uuid is None

    assert isinstance(recovered.children[1], SCMLoadHours)
    assert isinstance(recovered.children[1].strategy, SCMLoadHoursStrategy)
    assert recovered.children[1].strategy._energy_params.avg_power_W == 200

    assert isinstance(recovered.children[2], SCMLoadProfile)
    assert isinstance(recovered.children[2].strategy, SCMLoadProfileStrategy)
    assert recovered.children[2].strategy._energy_params.energy_profile.input_profile == "test.csv"
    assert recovered.children[2].strategy._energy_params.energy_profile.input_profile_uuid is None

    assert isinstance(recovered.children[3], SCMStorage)
    assert isinstance(recovered.children[3].strategy, SCMStorageStrategy)


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
