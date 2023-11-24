# pylint: disable=broad-except

from multiprocessing import Process, Queue

import pytest
from gsy_framework.enums import ConfigurationType
from pendulum import duration

from gsy_e.gsy_e_core.rq_job_handler import launch_simulation_from_rq_job


class TestRQJobUtils:
    """Test RQ-related utilities."""

    @staticmethod
    def fn(queue, **kwargs):
        # This helper function should not be defined in a local scope, so Python can dump it when
        # starting the process.
        """Launch simulation and push the exception in the result queue if any.
        This function is supposed to run in a separate process.
        """
        try:
            launch_simulation_from_rq_job(**kwargs)
        except Exception as exc:  # noqa
            queue.put(exc)
            raise exc

    def test_launch_simulation_from_rq_job(self):
        """Assure the launch_simulation_from_rq_job can successfully launch a simulation.
        The launch_simulation_from_rq_job is ran in another process to ensure that its changes on
        constant settings will not cause other tests to fail.
        """

        results_queue = Queue()
        process = Process(target=self.fn, args=(results_queue,), kwargs={
            "scenario": {
                "name": "Sample Scenario",
                "configuration_uuid": "25f55f48-d908-42d4-a7fb-1bc46877b3bf",
                "children": [
                    {
                        "name": "Infinite Bus", "type": "InfiniteBus",
                        "uuid": "91a4d9ba-625e-4a51-ba7e-2a3a97f68609"}]
            },
            "settings": {
               "duration": duration(days=1),
               "slot_length": duration(hours=1),
               "tick_length": duration(minutes=6),
               "type": ConfigurationType.SIMULATION.value
            },
            "events": None,
            "aggregator_device_mapping": {},
            "saved_state": {},
            "job_id": "TEST_SIM_RUNS",
            "connect_to_profiles_db": False
        })
        process.start()
        process.join()
        if process.exitcode != 0:
            pytest.fail(results_queue.get())
