import pickle
import zlib

from pendulum import duration

from gsy_e.gsy_e_core.rq_job_handler import launch_simulation_from_rq_job


class TestRQJobUtils:
    """Test RQ-related utilities."""
    @staticmethod
    def test_launch_simulation_from_rq_job():
        """Assure the launch_simulation_from_rq_job can successfully launch a simulation."""
        launch_simulation_from_rq_job(
            scenario=zlib.compress(pickle.dumps("default_2a")),
            settings={
                "sim_duration": duration(days=1),
                "slot_length": duration(hours=1),
                "tick_length": duration(minutes=6)
            },
            events=None,
            aggregator_device_mapping="null",
            saved_state=zlib.compress(pickle.dumps(None)),
            job_id="TEST_SIM_RUNS",
            connect_to_profiles_db=False
        )
