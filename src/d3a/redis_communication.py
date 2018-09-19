import os
import json
from logging import getLogger
from redis import StrictRedis
from redis.exceptions import ConnectionError

log = getLogger(__name__)


REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost')


class RedisSimulationCommunication:
    def __init__(self, simulation, simulation_id):
        if simulation_id is None:
            return
        self._simulation_id = simulation_id
        self._simulation = simulation
        self._sub_callback_dict = {self._simulation_id + "/reset": self._reset_callback,
                                   self._simulation_id + "/stop": self._stop_callback,
                                   self._simulation_id + "/pause": self._pause_callback,
                                   self._simulation_id + "/resume": self._resume_callback,
                                   self._simulation_id + "/slowdown": self._slowdown_callback}
        self.result_channel = "d3a-results"

        try:
            self.redis_db = StrictRedis.from_url(REDIS_URL)
            self.pubsub = self.redis_db.pubsub()
            self._subscribe_to_channels()
        except ConnectionError:
            log.error("Redis is not operational, will not use it for communication.")
            del self.pubsub
            return

    def _subscribe_to_channels(self):
        self.pubsub.subscribe(**self._sub_callback_dict)
        self.pubsub.run_in_thread(sleep_time=0.5, daemon=True)

    def _reset_callback(self, _):
        self._simulation.reset()

    def _stop_callback(self, _):
        self._simulation.stop()

    def _pause_callback(self, _):
        if not self._simulation.paused:
            self._simulation.toggle_pause()

    def _resume_callback(self, _):
        if self._simulation.paused:
            self._simulation.toggle_pause()

    def _slowdown_callback(self, message):
        data = json.loads(message["data"])
        slowdown = data.get('slowdown')
        if not slowdown:
            log.error("'slowdown' parameter missing from incoming message.")
            return
        try:
            slowdown = int(slowdown)
        except ValueError:
            log.error("'slowdown' parameter must be numeric")
            return
        if not -1 < slowdown < 101:
            log.error("'slowdown' must be in range 0 - 100")
            return
        self._simulation.slowdown = slowdown

    def publish_results(self, endpoint_buffer):
        if not hasattr(self, 'pubsub'):
            return
        self.redis_db.publish(self.result_channel,
                              json.dumps(endpoint_buffer.generate_result_report()))

    def publish_intermediate_results(self, endpoint_buffer):
        # Should have a different format in the future, hence the code duplication
        self.publish_results(endpoint_buffer)
