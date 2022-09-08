from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from gsy_framework.constants_limits import ConstSettings, GlobalConfig
from pendulum import DateTime, duration

from gsy_e.gsy_e_core.enums import FORWARD_MARKET_TYPES
from gsy_e.gsy_e_core.sim_results.endpoint_buffer import SimulationEndpointBuffer


@pytest.fixture(name="forward_setup")
def forward_setup_fixture():
    """Create area with all the forward markets and pre added timeslots for each forward market."""
    original_market_marker_rate = GlobalConfig.market_maker_rate
    original_enable_forward_markets = ConstSettings.ForwardMarketSettings.ENABLE_FORWARD_MARKETS
    GlobalConfig.market_maker_rate = 30
    ConstSettings.ForwardMarketSettings.ENABLE_FORWARD_MARKETS = True
    slot_length = duration(minutes=15)
    area = MagicMock(forward_markets={
        # each forward market will have 5 timeslots.
        market_type: MagicMock(market_time_slots=[
            f"TIME_SLOT_{i}" for i in range(5)
        ]) for market_type in FORWARD_MARKET_TYPES
    }, config=MagicMock(slot_length=slot_length), uuid="AREA")
    yield area, slot_length
    GlobalConfig.market_maker_rate = original_market_marker_rate
    ConstSettings.ForwardMarketSettings.ENABLE_FORWARD_MARKETS = original_enable_forward_markets


class TestSimulationEndpointBuffer:

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
            raw_results = endpoint_buffer.generate_result_report()["simulation_raw_data"]
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
