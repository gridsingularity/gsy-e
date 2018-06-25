import os
import json
from functools import wraps
from logging import getLogger
from redis import StrictRedis, ConnectionError

log = getLogger(__name__)


REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost')


def redis_error_muffle(func):
    @wraps
    def wrapper(cls, *args, **kwargs):
        try:
            return func(cls, *args, **kwargs)
        except ConnectionError:
            pass
    return wrapper


class RedisSimulationCommunication:
    def __init__(self, simulation, simulation_id):
        self._simulation_id = simulation_id
        self._simulation = simulation
        self.redis_db = StrictRedis.from_url(REDIS_URL)
        self.pubsub = self.redis_db.pubsub()
        self.result_channel = "d3a-results"
        self._subscribe_to_channels()

    def _subscribe_to_channels(self):
        self.pubsub.subscribe(**{self._simulation_id + "/reset": self._reset_callback,
                                 self._simulation_id + "/stop": self._stop_callback,
                                 self._simulation_id + "/pause": self._pause_callback,
                                 self._simulation_id + "/slowdown": self._slowdown_callback})
        self.pubsub.run_in_thread(sleep_time=0.5, daemon=True)

    def _reset_callback(self, _):
        self._simulation.reset()

    def _stop_callback(self, _):
        self._simulation.stop()

    def _pause_callback(self, _):
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
        self.redis_db.publish(self.result_channel,
                              json.dumps(endpoint_buffer.generate_result_report()))

    def publish_intermediate_results(self, endpoint_buffer):
        # Should have a different format in the future, hence the code duplication
        self.redis_db.publish(self.result_channel,
                              json.dumps(endpoint_buffer.generate_result_report()))
