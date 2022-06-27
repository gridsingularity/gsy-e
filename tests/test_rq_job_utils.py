# pylint: disable=broad-except

import pickle
import zlib
from multiprocessing import Process, Queue

import pytest
from pendulum import duration

from gsy_e.gsy_e_core.rq_job_handler import launch_simulation_from_rq_job


class TestRQJobUtils:
    """Test RQ-related utilities."""

    @staticmethod
    def test_launch_simulation_from_rq_job():
        """Assure the launch_simulation_from_rq_job can successfully launch a simulation.
        The launch_simulation_from_rq_job is ran in another process to ensure that its changes on
        constant settings will not cause other tests to fail.
        """

        def fn(queue, **kwargs):
            """Launch simulation and push the exception in the result queue if any.
            This function is supposed to run in a separate process.
            """
            try:
                launch_simulation_from_rq_job(**kwargs)
            except Exception as exc:  # noqa
                queue.put(exc)
                raise exc

        results_queue = Queue()
        process = Process(target=fn, args=(results_queue,), kwargs={
            "scenario": zlib.compress(pickle.dumps("default_2a")),
            "settings": {
                           "duration": duration(days=1),
                           "slot_length": duration(hours=1),
                           "tick_length": duration(minutes=6)
                       },
            "events": None,
            "aggregator_device_mapping": "null",
            "saved_state": zlib.compress(pickle.dumps(None)),
            "job_id": "TEST_SIM_RUNS",
            "connect_to_profiles_db": False
        })
        process.start()
        process.join()
        if process.exitcode != 0:
            pytest.fail(results_queue.get())
