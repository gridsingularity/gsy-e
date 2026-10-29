# pylint: disable=protected-access
import logging
from collections import defaultdict
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pendulum
import pytest
from gsy_framework.constants_limits import ConstSettings, GlobalConfig

from gsy_e.gsy_e_core.enums import FORWARD_MARKET_TYPES
from gsy_e.gsy_e_core.sim_results.endpoint_buffer import (
    SimulationEndpointBuffer,
)

logger = logging.getLogger(__name__)


@pytest.fixture(name="forward_setup")
def fixture_forward_setup():
    """Create area with all the forward markets and pre added timeslots for each forward market."""
    original_market_marker_rate = GlobalConfig.market_maker_rate
    original_enable_forward_markets = ConstSettings.ForwardMarketSettings.ENABLE_FORWARD_MARKETS
    GlobalConfig.market_maker_rate = 30
    ConstSettings.ForwardMarketSettings.ENABLE_FORWARD_MARKETS = True
    slot_length = pendulum.duration(minutes=15)
    forward_markets = {  # each forward market will have 5 timeslots.
        market_type: MagicMock(market_time_slots=[f"TIME_SLOT_{i}" for i in range(5)])
        for market_type in FORWARD_MARKET_TYPES
    }
    area = MagicMock(
        forward_markets=forward_markets,
        config=MagicMock(slot_length=slot_length),
        uuid="AREA",
        strategy=None,
    )
    area.name = "area-name"
    area.parent = None

    yield area, slot_length

    GlobalConfig.market_maker_rate = original_market_marker_rate
    ConstSettings.ForwardMarketSettings.ENABLE_FORWARD_MARKETS = original_enable_forward_markets


@pytest.fixture(name="general_setup")
def fixture_general_setup():
    """Create area with spot market"""
    general_market_maker_rate = GlobalConfig.market_maker_rate
    GlobalConfig.market_maker_rate = 30
    slot_length = pendulum.duration(minutes=15)
    area = MagicMock(config=MagicMock(slot_length=slot_length), uuid="AREA", strategy=None)
    area.name = "area-name"
    area.parent = None

    yield area, slot_length

    GlobalConfig.market_maker_rate = general_market_maker_rate


@pytest.fixture(name="setup_multiple_levels")
def fixture_setup_multiple_levels():
    """Setup with multiple levels"""
    area = MagicMock(
        name="Grid",
        children=[
            MagicMock(
                name="City 1",
                children=[
                    MagicMock(
                        name="Community 1",
                        children=[
                            MagicMock(
                                name="House 1",
                                children=[
                                    MagicMock(name="Load", children=[]),
                                    MagicMock(name="PV", children=[]),
                                ],
                            ),
                            MagicMock(
                                name="House 2",
                                children=[
                                    MagicMock(name="Load", children=[]),
                                    MagicMock(name="PV", children=[]),
                                ],
                            ),
                        ],
                    ),
                    MagicMock(
                        name="Community 2",
                        children=[
                            MagicMock(
                                name="House 1",
                                children=[
                                    MagicMock(name="Load", children=[]),
                                    MagicMock(name="PV", children=[]),
                                ],
                            ),
                            MagicMock(
                                name="House 2",
                                children=[
                                    MagicMock(name="Load", children=[]),
                                    MagicMock(name="PV", children=[]),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
            MagicMock(
                name="City 2",
                children=[
                    MagicMock(
                        name="Community 3",
                        children=[
                            MagicMock(
                                name="House 1",
                                children=[
                                    MagicMock(name="Load", children=[]),
                                    MagicMock(name="PV", children=[]),
                                ],
                            ),
                            MagicMock(
                                name="House 2",
                                children=[
                                    MagicMock(name="Load", children=[]),
                                    MagicMock(name="PV", children=[]),
                                ],
                            ),
                        ],
                    ),
                    MagicMock(
                        name="Community 4",
                        children=[
                            MagicMock(
                                name="House 1",
                                children=[
                                    MagicMock(name="Load", children=[]),
                                    MagicMock(name="PV", children=[]),
                                ],
                            ),
                            MagicMock(
                                name="House 2",
                                children=[
                                    MagicMock(name="Load", children=[]),
                                    MagicMock(name="PV", children=[]),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )

    yield area


class TestSimulationEndpointBuffer:
    """Test for the normal simulations of SimulationEndpointBuffer class"""

    @staticmethod
    def _generate_order(creation_time, time_slot):
        """Generate one mock order{bid,offer,trade}."""
        return MagicMock(
            creation_time=creation_time,
            time_slot=time_slot,
            serializable_dict=lambda: {"creation_time": creation_time, "time_slot": time_slot},
        )

    def test_prepare_results_for_publish_creates_dict_successfully(self, general_setup):
        area, _ = general_setup
        endpoint_buffer = SimulationEndpointBuffer(
            job_id="JOB_1", random_seed=41, area=area, should_export_plots=False
        )

        output = endpoint_buffer.prepare_results_for_publish()

        assert output == {
            "job_id": "JOB_1",
            "current_market": "",
            "current_market_ui_time_slot_str": "",
            "random_seed": 41,
            "status": "",
            "progress_info": {
                "eta_seconds": 0,
                "elapsed_time_seconds": 0,
                "percentage_completed": 0,
            },
            "results_area_uuids": [],
            "simulation_state": {"general": {}, "areas": {}},
            "simulation_raw_data": {},
            "configuration_tree": {
                "name": "area-name",
                "uuid": "AREA",
                "parent_uuid": "",
                "type": "Area",
                "children": [],
            },
        }

    @patch("gsy_e.gsy_e_core.sim_results.endpoint_buffer.get_json_dict_memory_allocation_size")
    def test_prepare_results_for_publish_output_too_big(
        self, get_json_dict_memory_allocation_size_mock, general_setup, caplog
    ):
        """The preparation of results fails if the output is too big."""
        area, _ = general_setup
        endpoint_buffer = SimulationEndpointBuffer(
            job_id="JOB_1", random_seed=41, area=area, should_export_plots=False
        )

        get_json_dict_memory_allocation_size_mock.return_value = 128000
        with caplog.at_level(logging.WARNING):
            output = endpoint_buffer.prepare_results_for_publish()
            assert (
                "Do not publish message bigger than 64 MB, current message size 128.0 MB."
                in caplog.text
            )

        assert not output

    def test_generate_json_report_returns_successfully(self, general_setup):
        area, _ = general_setup
        endpoint_buffer = SimulationEndpointBuffer(
            job_id="JOB_1", random_seed=41, area=area, should_export_plots=False
        )

        # The ResultsHandler class should be tested as a different unit, so we just mock its output
        results_handler_mock = MagicMock(all_raw_results={"mocked-results": "some-results"})
        endpoint_buffer.results_handler = results_handler_mock

        assert endpoint_buffer.generate_json_report() == {
            "hierarchy_self_consumption_percent": {},
            "job_id": "JOB_1",
            "random_seed": 41,
            "status": "",
            "progress_info": {
                "eta_seconds": 0,
                "elapsed_time_seconds": 0,
                "percentage_completed": 0,
            },
            "simulation_state": {"general": {}, "areas": {}},
            "mocked-results": "some-results",
        }

    def test_update_stats_spot_markets_updates_successfully(self, general_setup):
        # pylint: disable=protected-access
        area, _ = general_setup
        area.spot_market = MagicMock(
            name="current-market",
            time_slot=pendulum.DateTime(2022, 10, 30),
            time_slot_str="2021-10-30T00:00:00+00:00",
        )

        # Popoulate strategy and children to update the result_area_uuids dictionary
        child_1 = MagicMock(uuid="child-uuid-1")
        child_1.name = "child_1"
        child_1.strategy = MagicMock()
        child_1.parent = area
        child_2 = MagicMock(uuid="child-uuid-2")
        child_2.name = "child_2"
        child_2.strategy = MagicMock()
        child_2.parent = area

        area.children = [child_1, child_2]

        endpoint_buffer = SimulationEndpointBuffer(
            job_id="JOB_1", random_seed=41, area=area, should_export_plots=False
        )

        endpoint_buffer._populate_core_stats_and_sim_state = MagicMock()

        sim_state_mock = MagicMock(name="sim-state")
        progress_info_mock = MagicMock(
            name="progress-info",
            eta=pendulum.duration(minutes=15),
            elapsed_time=pendulum.duration(minutes=30),
            percentage_complete=1,
        )

        endpoint_buffer.update_stats(
            area=area,
            simulation_status="some-state",
            progress_info=progress_info_mock,
            sim_state=sim_state_mock,
            calculate_results=False,
        )

        assert endpoint_buffer.area_result_dict == {
            "name": "area-name",
            "uuid": "AREA",
            "parent_uuid": "",
            "type": "Area",
            "children": [
                {
                    "children": [],
                    "name": "child_1",
                    "parent_uuid": "AREA",
                    "type": "MagicMock",
                    "uuid": "child-uuid-1",
                },
                {
                    "children": [],
                    "name": "child_2",
                    "parent_uuid": "AREA",
                    "type": "MagicMock",
                    "uuid": "child-uuid-2",
                },
            ],
        }

        assert endpoint_buffer.status == "some-state"
        assert endpoint_buffer.simulation_state["general"] == sim_state_mock

        assert endpoint_buffer.spot_market_time_slot_str == "2021-10-30T00:00:00+00:00"
        assert endpoint_buffer.spot_market_ui_time_slot_str == "October 30 2022, 00:00 h"
        assert endpoint_buffer.spot_market_time_slot == pendulum.DateTime(2022, 10, 30)

        endpoint_buffer._populate_core_stats_and_sim_state.assert_called_once_with(area)
        assert endpoint_buffer.simulation_progress == {
            "eta_seconds": 900,
            "elapsed_time_seconds": 1800,
            "percentage_completed": 1,
        }

        assert endpoint_buffer.result_area_uuids == {"AREA", "child-uuid-2", "child-uuid-1"}

    @staticmethod
    def _create_kpis(area):
        kpis = defaultdict(dict)
        for n_city, city in enumerate(area.children):
            kpis[city.uuid]["self_consumption"] = (n_city + 2) * 10
            for n_community, community in enumerate(city.children):
                kpis[community.uuid]["self_consumption"] = (n_community + 1) * 10
                for n_house, house in enumerate(community.children):
                    kpis[house.uuid]["self_consumption"] = n_house * 10
        return kpis

    def test_create_hierarchy_stats_returns_correct_results(self, setup_multiple_levels):
        kpis = self._create_kpis(setup_multiple_levels)
        endpoint_buffer = SimulationEndpointBuffer(
            job_id="JOB_1", random_seed=41, should_export_plots=False, area=setup_multiple_levels
        )
        endpoint_buffer.results_handler.results_mapping["kpi"].performance_indices_redis = kpis
        endpoint_buffer.create_hierarchy_stats(setup_multiple_levels)

        assert endpoint_buffer.hierarchy_self_consumption_percent == {0: 40, 1: 40, 2: 20}


class TestSimulationEndpointBufferForward:
    """Tests for the SimulationEndpointBuffer class."""

    @staticmethod
    def _generate_order(creation_time, time_slot):
        """Generate one mock order{bid,offer,trade}."""
        return MagicMock(
            creation_time=creation_time,
            time_slot=time_slot,
            serializable_dict=lambda: {"creation_time": creation_time, "time_slot": time_slot},
        )

    @patch(
        "gsy_e.gsy_e_core.sim_results.endpoint_buffer.SimulationResultValidator."
        "validate_simulation_raw_data",
        lambda self, data: True,
    )
    def test_forward_results_are_generated(  # pylint: disable-msg=too-many-locals
        self, forward_setup
    ):
        """Test results are being correctly generated with respect to
        forward market timeslots and current market timeslot."""
        area, slot_length = forward_setup

        progress_info = MagicMock()
        endpoint_buffer = SimulationEndpointBuffer("JOB_1", 41, area, False)

        # add bids/offers/trades for 3 consequent slots for all forward timeslots.
        start_time = pendulum.DateTime(2020, 1, 1, 0, 15)
        for market in area.forward_markets.values():
            current_time = start_time

            market.bids = {}
            market.offers = {}
            market.trades = []

            for _ in range(3):
                for i in range(5):
                    market.bids[uuid4()] = self._generate_order(
                        creation_time=current_time - slot_length, time_slot=f"TIME_SLOT_{i}"
                    )

                    market.offers[uuid4()] = self._generate_order(
                        creation_time=current_time - slot_length, time_slot=f"TIME_SLOT_{i}"
                    )

                market.trades.extend(
                    [
                        self._generate_order(
                            creation_time=current_time - slot_length, time_slot=f"TIME_SLOT_{i}"
                        )
                        for i in range(5)
                    ]
                )
                current_time += slot_length

        # update the endpoint buffer for each of the 3 timeslots and
        # check results are generated correctly.
        current_time = start_time
        for _ in range(3):
            area.now = current_time
            endpoint_buffer.update_stats(area, "running", progress_info, {}, False)
            # pylint: disable=protected-access
            raw_results = endpoint_buffer._generate_result_report()["simulation_raw_data"]
            area_forward_stats = raw_results[area.uuid]["forward_market_stats"]

            for market_type in FORWARD_MARKET_TYPES:
                market_stats = area_forward_stats[market_type.value]
                for i in range(5):
                    timeslot_stats = market_stats[f"TIME_SLOT_{i}"]
                    for order_type in ("bids", "offers", "trades"):
                        orders = timeslot_stats[order_type]
                        assert len(orders) == 1
                        assert orders[0]["time_slot"] == f"TIME_SLOT_{i}"
                        assert (
                            current_time - slot_length <= orders[0]["creation_time"] < current_time
                        )
            current_time += slot_length

    def test_prepare_results_for_publish(self, forward_setup):
        area, _ = forward_setup
        endpoint_buffer = SimulationEndpointBuffer(
            job_id="JOB_1", random_seed=41, area=area, should_export_plots=False
        )

        output = endpoint_buffer.prepare_results_for_publish()

        assert output == {
            "job_id": "JOB_1",
            "current_market": "",
            "current_market_ui_time_slot_str": "",
            "random_seed": 41,
            "status": "",
            "progress_info": {
                "eta_seconds": 0,
                "elapsed_time_seconds": 0,
                "percentage_completed": 0,
            },
            "results_area_uuids": [],
            "simulation_state": {"general": {}, "areas": {}},
            "simulation_raw_data": {},
            "configuration_tree": {
                "name": "area-name",
                "uuid": "AREA",
                "parent_uuid": "",
                "type": "Area",
                "children": [],
            },
        }

    @patch("gsy_e.gsy_e_core.sim_results.endpoint_buffer.get_json_dict_memory_allocation_size")
    def test_prepare_results_for_publish_output_too_big(
        self, get_json_dict_memory_allocation_size_mock, forward_setup, caplog
    ):
        """The preparation of results fails if the output is too big."""
        area, _ = forward_setup
        endpoint_buffer = SimulationEndpointBuffer(
            job_id="JOB_1", random_seed=41, area=area, should_export_plots=False
        )

        get_json_dict_memory_allocation_size_mock.return_value = 128000
        with caplog.at_level(logging.WARNING):
            output = endpoint_buffer.prepare_results_for_publish()
            assert (
                "Do not publish message bigger than 64 MB, current message size 128.0 MB."
                in caplog.text
            )

        assert not output

    def test_generate_json_report_returns_successfully(self, forward_setup):
        area, _ = forward_setup
        endpoint_buffer = SimulationEndpointBuffer(
            job_id="JOB_1", random_seed=41, area=area, should_export_plots=False
        )

        # The ResultsHandler class should be tested as a different unit, so we just mock its output
        results_handler_mock = MagicMock(all_raw_results={"mocked-results": "some-results"})
        endpoint_buffer.results_handler = results_handler_mock

        assert endpoint_buffer.generate_json_report() == {
            "hierarchy_self_consumption_percent": {},
            "job_id": "JOB_1",
            "random_seed": 41,
            "status": "",
            "progress_info": {
                "eta_seconds": 0,
                "elapsed_time_seconds": 0,
                "percentage_completed": 0,
            },
            "simulation_state": {"general": {}, "areas": {}},
            "mocked-results": "some-results",
        }

    def test_update_stats_forward_markets_updated_successfully(self, forward_setup):
        # pylint: disable=protected-access
        area, _ = forward_setup
        area.spot_market = MagicMock(
            name="current-market",
            time_slot=pendulum.DateTime(2022, 10, 30),
            time_slot_str="2021-10-30T00:00:00+00:00",
        )

        # Popoulate strategy and children to update the result_area_uuids dictionary
        child_1 = MagicMock(uuid="child-uuid-1")
        child_1.name = "child_1"
        child_1.strategy = MagicMock(_energy_params=MagicMock(capacity_kW=2))
        child_1.parent = area
        child_2 = MagicMock(uuid="child-uuid-2")
        child_2.name = "child_2"
        child_2.strategy = MagicMock(_energy_params=MagicMock(capacity_kW=1.5))
        child_2.parent = area

        area.children = [child_1, child_2]

        endpoint_buffer = SimulationEndpointBuffer(
            job_id="JOB_1", random_seed=41, area=area, should_export_plots=False
        )

        # We mock this method because it would be too complex to test all its conditionals here.
        # It would be good to refactor the method into a class and test it independently for each
        # market type (settlement, future, forward).
        endpoint_buffer._populate_core_stats_and_sim_state = MagicMock()

        sim_state_mock = MagicMock(name="sim-state")
        progress_info_mock = MagicMock(
            name="progress-info",
            eta=pendulum.duration(minutes=15),
            elapsed_time=pendulum.duration(minutes=30),
            percentage_complete=1,
        )

        endpoint_buffer.update_stats(
            area=area,
            simulation_status="some-state",
            progress_info=progress_info_mock,
            sim_state=sim_state_mock,
            calculate_results=False,
        )

        assert endpoint_buffer.area_result_dict == {
            "name": "area-name",
            "uuid": "AREA",
            "parent_uuid": "",
            "type": "Area",
            "children": [
                {
                    "children": [],
                    "name": "child_1",
                    "parent_uuid": "AREA",
                    "type": "MagicMock",
                    "uuid": "child-uuid-1",
                    "capacity_kW": 2,
                },
                {
                    "children": [],
                    "name": "child_2",
                    "parent_uuid": "AREA",
                    "type": "MagicMock",
                    "uuid": "child-uuid-2",
                    "capacity_kW": 1.5,
                },
            ],
        }
        assert endpoint_buffer.status == "some-state"
        assert endpoint_buffer.simulation_state["general"] == sim_state_mock

        assert endpoint_buffer.spot_market_time_slot_str == "2021-10-30T00:00:00+00:00"
        assert endpoint_buffer.spot_market_ui_time_slot_str == "October 30 2022, 00:00 h"
        assert endpoint_buffer.spot_market_time_slot == pendulum.DateTime(2022, 10, 30)

        endpoint_buffer._populate_core_stats_and_sim_state.assert_called_once_with(area)
        assert endpoint_buffer.simulation_progress == {
            "eta_seconds": 900,
            "elapsed_time_seconds": 1800,
            "percentage_completed": 1,
        }

        assert endpoint_buffer.result_area_uuids == {"AREA", "child-uuid-2", "child-uuid-1"}

    @pytest.mark.parametrize("non_p2p", [True, False])
    def test_update_stats_sets_no_p2p_correctly(self, forward_setup, non_p2p):
        # pylint: disable=protected-access
        area, _ = forward_setup
        area.spot_market = MagicMock(
            name="current-market",
            time_slot=pendulum.DateTime(2022, 10, 30),
            time_slot_str="2021-10-30T00:00:00+00:00",
        )

        # Popoulate strategy and children to update the result_area_uuids dictionary
        child_1 = MagicMock(uuid="child-uuid-1")
        child_1.name = "child_1"
        child_1.strategy = MagicMock(_energy_params=MagicMock(capacity_kW=2))
        child_1.parent = area
        child_2 = MagicMock(uuid="child-uuid-2")
        child_2.name = "child_2"
        child_2.strategy = MagicMock(_energy_params=MagicMock(capacity_kW=1.5))
        child_2.parent = area

        area.children = [child_1, child_2]

        endpoint_buffer = SimulationEndpointBuffer(
            job_id="JOB_1", random_seed=41, area=area, should_export_plots=False
        )

        # We mock this method because it would be too complex to test all its conditionals here.
        # It would be good to refactor the method into a class and test it independently for each
        # market type (settlement, future, forward).
        endpoint_buffer._populate_core_stats_and_sim_state = MagicMock()

        sim_state_mock = MagicMock(name="sim-state")
        progress_info_mock = MagicMock(
            name="progress-info",
            eta=pendulum.duration(minutes=15),
            elapsed_time=pendulum.duration(minutes=30),
            percentage_complete=1,
        )

        with patch("gsy_e.constants.RUN_IN_NON_P2P_MODE", non_p2p):
            endpoint_buffer.update_stats(
                area=area,
                simulation_status="some-state",
                progress_info=progress_info_mock,
                sim_state=sim_state_mock,
                calculate_results=False,
            )
        if non_p2p:
            assert endpoint_buffer.area_result_dict["non_p2p"]
        else:
            assert "non_p2p" not in endpoint_buffer.area_result_dict
        for child in endpoint_buffer.area_result_dict["children"]:
            if non_p2p:
                assert child["non_p2p"]
            else:
                assert "non_p2p" not in child
