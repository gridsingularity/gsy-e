# pylint: disable=protected-access
import logging
from unittest.mock import MagicMock

import pendulum
from pendulum import datetime

from scm.core.results.endpoint_buffer import CoefficientEndpointBuffer
from scm.scm_manager import SCMManager

logger = logging.getLogger(__name__)


class TestCoefficientEndpointBuffer:
    """Tests for the CoefficientEndpointBuffer class."""

    @staticmethod
    def test_update_stats_scm_updated_successfully(scm_setup):
        coefficient_area, _ = scm_setup

        endpoint_buffer = CoefficientEndpointBuffer(
            job_id="JOB_1", random_seed=41, area=coefficient_area, should_export_plots=False
        )

        endpoint_buffer._populate_core_stats_and_sim_state = MagicMock()

        sim_state_mock = MagicMock(name="sim-state")
        progress_info_mock = MagicMock(
            name="progress-info",
            eta=pendulum.duration(minutes=15),
            elapsed_time=pendulum.duration(minutes=30),
            percentage_complete=1,
        )

        endpoint_buffer.update_coefficient_stats(
            area=coefficient_area,
            simulation_status="some-state",
            progress_info=progress_info_mock,
            sim_state=sim_state_mock,
            scm_manager=SCMManager(area=coefficient_area, time_slot=datetime(2022, 10, 30)),
            calculate_results=False,
        )

        assert isinstance(endpoint_buffer._scm_manager, SCMManager)
        assert endpoint_buffer.spot_market_time_slot_str == progress_info_mock.current_slot_str
        assert endpoint_buffer.spot_market_time_slot == progress_info_mock.current_slot_time
        assert (
            endpoint_buffer.spot_market_time_slot_unix
            == progress_info_mock.current_slot_time.timestamp()
        )
