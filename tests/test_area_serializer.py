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
import json
from datetime import datetime

import pytest
from d3a.gsy_core.area_serializer import area_to_string, area_from_string, are_all_areas_unique
from d3a.models.area import Area
from d3a.models.config import SimulationConfig
from d3a.models.leaves import SmartMeter, PV, LoadHours, Storage
from d3a.models.strategy.external_strategies.load import LoadHoursExternalStrategy
from d3a.models.strategy.external_strategies.pv import PVExternalStrategy
from d3a.models.strategy.external_strategies.storage import StorageExternalStrategy
from d3a.models.strategy.smart_meter import SmartMeterStrategy
from d3a.models.strategy.pv import PVStrategy
from d3a_interface.constants_limits import ConstSettings, GlobalConfig
from pendulum import duration, instance


def create_config(settings={}):
    config_settings = {
        "start_date":
            instance(datetime.combine(settings.get("start_date"), datetime.min.time()))
            if "start_date" in settings else GlobalConfig.start_date,
        "sim_duration":
            duration(days=settings["duration"].days)
            if "duration" in settings else GlobalConfig.sim_duration,
        "slot_length":
            duration(seconds=settings["slot_length"].seconds)
            if "slot_length" in settings else GlobalConfig.slot_length,
        "tick_length":
            duration(seconds=settings["tick_length"].seconds)
            if "tick_length" in settings else GlobalConfig.tick_length,
        "market_maker_rate":
            settings.get("market_maker_rate",
                         str(ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE)),
        "cloud_coverage": settings.get("cloud_coverage", GlobalConfig.cloud_coverage),
        "pv_user_profile": settings.get("pv_user_profile", None),
        "capacity_kW": settings.get("capacity_kW",
                                    ConstSettings.PVSettings.DEFAULT_CAPACITY_KW),
        "grid_fee_type": settings.get("grid_fee_type", GlobalConfig.grid_fee_type),
        "external_connection_enabled": settings.get("external_connection_enabled", False),
        "aggregator_device_mapping": None
    }
    return SimulationConfig(**config_settings)


def test_area_with_children_roundtrip():
    child1 = Area("child1")
    child2 = Area("child2")
    parent = Area("parent", [child1, child2])
    string = area_to_string(parent)
    recovered = area_from_string(string, create_config())
    assert recovered.name == "parent"
    assert recovered.children[0].name == "child1"
    assert recovered.children[1].name == "child2"


def test_raises_unknown_class():
    with pytest.raises(ValueError):
        area_from_string("{'name':'broken','strategy':'NonexistentStrategy'}", create_config())


def test_strategy_roundtrip_with_params():
    area = Area('area', [], None, PVStrategy(panel_count=42))
    area_str = area_to_string(area)
    recovered = area_from_string(area_str, create_config())
    assert recovered.strategy.panel_count == 42


def test_non_attr_param():
    area1 = Area('area1', [], None, PVStrategy())
    recovered1 = area_from_string(area_to_string(area1), create_config())
    assert recovered1.strategy.capacity_kW is None
    assert recovered1.strategy.offer_update.final_rate_profile_buffer[area1.config.start_date] == \
        ConstSettings.PVSettings.SELLING_RATE_RANGE.final


def test_leaf_deserialization():
    recovered = area_from_string(
        '''{
             "name": "house",
             "children":[
                 {"name": "pv1", "type": "PV", "panel_count": 4, "display_type": "PV"},
                 {"name": "pv2", "type": "PV", "panel_count": 1, "display_type": "PV"},
                 {"name": "smart meter", "type": "SmartMeter",
                  "smart_meter_profile": "some_path.csv"}
             ]
           }
        ''',
        config=create_config()
    )
    pv1, pv2, smart_meter = recovered.children
    assert isinstance(pv1, PV)
    assert pv1.strategy.panel_count == 4
    assert pv1.display_type == "PV"
    assert isinstance(pv2, PV)
    assert pv2.strategy.panel_count == 1
    assert pv2.display_type == "PV"
    assert isinstance(smart_meter, SmartMeter)


def test_leaf_external_connection_deserialization():
    recovered = area_from_string(
        '''{
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
        ''',
        create_config({"external_connection_enabled": True})
    )

    pv1, load1, storage1 = recovered.children
    assert isinstance(pv1, PV)
    assert isinstance(pv1.strategy, PVExternalStrategy)
    assert pv1.strategy.panel_count == 4
    assert pv1.display_type == "PV"
    assert isinstance(load1, LoadHours)
    assert isinstance(load1.strategy, LoadHoursExternalStrategy)
    assert load1.strategy.avg_power_W == 200
    assert load1.display_type == "Load"
    assert isinstance(storage1, Storage)
    assert isinstance(storage1.strategy, StorageExternalStrategy)
    assert storage1.display_type == "Storage"


@pytest.fixture
def fixture_with_leaves():
    area = Area("house", [
        PV("pv1", panel_count=1, config=create_config()),
        PV("pv2", panel_count=4, config=create_config()),
        SmartMeter("smart meter", smart_meter_profile="some_path.csv", config=create_config()),
    ])
    return area_to_string(area)


def test_leaf_serialization(fixture_with_leaves):
    description = json.loads(fixture_with_leaves)
    assert len(description["children"]) == 3
    assert description['children'][0]['type'] == 'PV'
    assert description['children'][0]['panel_count'] == 1
    assert description['children'][1]['type'] == 'PV'
    assert description['children'][1]['panel_count'] == 4
    assert description['children'][2]['type'] == 'SmartMeter'


def test_roundtrip_with_leaf(fixture_with_leaves):
    recovered = area_from_string(fixture_with_leaves, create_config())
    assert isinstance(recovered.children[0].strategy, PVStrategy)
    assert isinstance(recovered.children[1].strategy, PVStrategy)
    assert isinstance(recovered.children[2].strategy, SmartMeterStrategy)


def test_area_does_not_allow_duplicate_subarea_names():
    area = Area(
        'Grid',
        [Area('House 1', children=[Area('H1 General Load'), Area('H1 PV1')]),
         Area('House 1', children=[Area('H2 General Load'), Area('H2 PV1')])],
    )

    with pytest.raises(AssertionError):
        are_all_areas_unique(area, set())

    area = Area(
        'Grid',
        [Area('House 1', children=[Area('H1 General Load'), Area('H1 PV1')]),
         Area('House 2', children=[Area('H1 General Load'), Area('H2 PV1')])],
    )

    with pytest.raises(AssertionError):
        are_all_areas_unique(area, set())

    area = Area(
        'Grid',
        [Area('House 1', children=[Area('H1 General Load'), Area('H1 PV1')]),
         Area('House 2', children=[Area('H2 General Load'), Area('H2 PV1')])],
    )

    # Does not raise an assertion
    are_all_areas_unique(area, set())
