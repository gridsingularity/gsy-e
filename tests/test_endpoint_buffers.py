import logging
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from gsy_framework.constants_limits import ConstSettings, GlobalConfig
from pendulum import DateTime, duration

from gsy_e.gsy_e_core.enums import FORWARD_MARKET_TYPES
from gsy_e.gsy_e_core.sim_results.endpoint_buffer import SimulationEndpointBuffer

logger = logging.getLogger(__name__)


@pytest.fixture(name="forward_setup")
def forward_setup_fixture():
    """Create area with all the forward markets and pre added timeslots for each forward market."""
    original_market_marker_rate = GlobalConfig.market_maker_rate
    original_enable_forward_markets = ConstSettings.ForwardMarketSettings.ENABLE_FORWARD_MARKETS
    GlobalConfig.market_maker_rate = 30
    ConstSettings.ForwardMarketSettings.ENABLE_FORWARD_MARKETS = True
    slot_length = duration(minutes=15)
    forward_markets = {  # each forward market will have 5 timeslots.
        market_type: MagicMock(market_time_slots=[f"TIME_SLOT_{i}" for i in range(5)])
        for market_type in FORWARD_MARKET_TYPES
    }
    area = MagicMock(
        forward_markets=forward_markets,
        config=MagicMock(slot_length=slot_length),
        uuid="AREA")
    area.name = "area-name"
    area.parent = None

    yield area, slot_length

    GlobalConfig.market_maker_rate = original_market_marker_rate
    ConstSettings.ForwardMarketSettings.ENABLE_FORWARD_MARKETS = original_enable_forward_markets


class TestSimulationEndpointBuffer:
    """Tests for the SimulationEndpointBuffer class."""

    # pylint: disable=no-self-use
    @staticmethod
    def _generate_order(creation_time, time_slot):
        """Generate one mock order{bid,offer,trade}."""
        return MagicMock(
            creation_time=creation_time,
            time_slot=time_slot,
            serializable_dict=lambda: {
                "creation_time": creation_time, "time_slot": time_slot})

    def test_forward_results_are_generated(   # pylint: disable-msg=too-many-locals
            self, forward_setup):
        """Test results are being correctly generated with respect to
        forward market timeslots and current market timeslot."""
        area, slot_length = forward_setup

        progress_info = MagicMock()
        endpoint_buffer = SimulationEndpointBuffer("JOB_1", 41, area, False)

        # add bids/offers/trades for 3 consequent slots for all forward timeslots.
        start_time = DateTime(2020, 1, 1, 0, 15)
        for market in area.forward_markets.values():
            current_time = start_time

            market.bids = {}
            market.offers = {}
            market.trades = []

            for _ in range(3):
                for i in range(5):
                    market.bids[uuid4()] = self._generate_order(
                        creation_time=current_time - slot_length,
                        time_slot=f"TIME_SLOT_{i}")

                    market.offers[uuid4()] = self._generate_order(
                        creation_time=current_time - slot_length,
                        time_slot=f"TIME_SLOT_{i}")

                market.trades.extend([
                    self._generate_order(
                        creation_time=current_time - slot_length,
                        time_slot=f"TIME_SLOT_{i}") for i in range(5)])
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
                        assert (current_time - slot_length <=
                                orders[0]["creation_time"] < current_time)
            current_time += slot_length

    def test_prepare_results_for_publish(self, forward_setup):
        area, _ = forward_setup
        endpoint_buffer = SimulationEndpointBuffer(
            job_id="JOB_1",
            random_seed=41,
            area=area,
            should_export_plots=False)

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
            "bids_offers_trades": {},
            "results_area_uuids": [],
            "simulation_state": {"general": {}, "areas": {}},
            "simulation_raw_data": {},
            "configuration_tree": {
                "name": "area-name",
                "uuid": "AREA",
                "parent_uuid": "",
                "type": "MagicMock",
                "children": []
            }
        }

    @patch("gsy_e.gsy_e_core.sim_results.endpoint_buffer.get_json_dict_memory_allocation_size")
    def test_prepare_results_for_publish_output_too_big(
            self, get_json_dict_memory_allocation_size_mock, forward_setup, caplog):
        """The preparation of results fails if the output is too big."""

        area, _ = forward_setup
        endpoint_buffer = SimulationEndpointBuffer(
            job_id="JOB_1",
            random_seed=41,
            area=area,
            should_export_plots=False)

        get_json_dict_memory_allocation_size_mock.return_value = 128000
        with caplog.at_level(logging.WARNING):
            output = endpoint_buffer.prepare_results_for_publish()
            assert "Do not publish message bigger than 64 MB, current message size 128.0 MB." \
                in caplog.text

        assert output == {}

    def test_generate_json_report(self, forward_setup):
        area, _ = forward_setup
        endpoint_buffer = SimulationEndpointBuffer(
            job_id="JOB_1",
            random_seed=41,
            area=area,
            should_export_plots=False)

        # The ResultsHandler class should be tested as a different unit, so we just mock its output
        results_handler_mock = MagicMock(all_raw_results={"mocked-results": "some-results"})
        endpoint_buffer.results_handler = results_handler_mock

        assert endpoint_buffer.generate_json_report() == {
            "job_id": "JOB_1",
            "random_seed": 41,
            "status": "",
            "progress_info": {
                "eta_seconds": 0,
                "elapsed_time_seconds": 0,
                "percentage_completed": 0
            },
            "simulation_state": {"general": {}, "areas": {}},
            "mocked-results": "some-results"
        }


class TestCoefficientEndpointBuffer(TestSimulationEndpointBuffer):
    """Tests for the CoefficientEndpointBuffer class.

    Run the same tests as TestSimulationEndpointBuffer to make sure that the Liskov substitution
    principle is respected and both classes can operate successfully.
    """
