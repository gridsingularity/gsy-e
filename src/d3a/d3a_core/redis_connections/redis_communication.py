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
import os
import json
from logging import getLogger
from redis import StrictRedis
from redis.exceptions import ConnectionError
from rq import get_current_job
from rq.exceptions import NoSuchJobError
from d3a_interface.results_validator import results_validator
from zlib import compress

log = getLogger(__name__)


REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost')

ERROR_CHANNEL = "d3a-errors"
RESULTS_CHANNEL = "d3a-results"
ZIP_RESULTS_CHANNEL = "d3a-zip-results"
ZIP_RESULTS_KEY = "d3a-zip-results-key/"


def utf8len(s):
    return len(s.encode('utf-8')) / 1000.0


class RedisSimulationCommunication:
    def __init__(self, simulation, simulation_id, live_events):
        if simulation_id is None:
            return
        self._live_events = live_events
        self._simulation_id = simulation_id
        self._simulation = simulation
        self._sub_callback_dict = {self._simulation_id + "/stop": self._stop_callback,
                                   self._simulation_id + "/pause": self._pause_callback,
                                   self._simulation_id + "/resume": self._resume_callback,
                                   self._simulation_id + "/slowdown": self._slowdown_callback}
        self.result_channel = RESULTS_CHANNEL

        try:
            self.redis_db = StrictRedis.from_url(REDIS_URL, retry_on_timeout=True)
            self.pubsub = self.redis_db.pubsub()
            self._subscribe_to_channels()
        except ConnectionError:
            log.error("Redis is not operational, will not use it for communication.")
            del self.pubsub
            return

    def _subscribe_to_channels(self):
        self.pubsub.subscribe(**self._sub_callback_dict)
        self.pubsub.run_in_thread(sleep_time=0.5, daemon=True)

    def _generate_redis_response(self, response, simulation_id, is_successful, command_type):
        stop_response_channel = f'{simulation_id}/response/stop'
        if is_successful:
            self.publish_json(
                stop_response_channel,
                {
                    "command": str(command_type), "status": "success",
                    "simulation_id": str(self._simulation_id),
                    "transaction_id": response["transaction_id"]})
        else:
            self.publish_json(
                stop_response_channel,
                {
                    "command": str(command_type), "status": "error",
                    "simulation_id": str(self._simulation_id),
                    "error_message": f"Error when handling simulation {command_type}.",
                    "transaction_id": response["transaction_id"]})

    def _stop_callback(self, payload):
        response = json.loads(payload["data"])
        self._simulation.stop()
        self._generate_redis_response(
            response, self._simulation_id, self._simulation.is_stopped, "stop"
        )

    def _pause_callback(self, payload):
        response = json.loads(payload["data"])

        if not self._simulation.paused:
            self._simulation.toggle_pause()
        self._generate_redis_response(
            response, self._simulation_id, self._simulation.paused, "pause"
        )
        log.info(f"Simulation with job_id: {self._simulation_id} is paused.")

    def _resume_callback(self, payload):
        response = json.loads(payload["data"])
        if self._simulation.paused:
            self._simulation.toggle_pause()
        self._generate_redis_response(
            response, self._simulation_id, not self._simulation.paused, "resume"
        )
        log.info(f"Simulation with job_id: {self._simulation_id} is resumed.")

    def _slowdown_callback(self, message):
        data = json.loads(message["data"])
        slowdown = data.get('slowdown')
        if not slowdown:
            log.warning("'slowdown' parameter missing from incoming message.")
            return
        try:
            slowdown = int(slowdown)
        except ValueError:
            log.warning("'slowdown' parameter must be numeric")
            return
        if not -1 < slowdown < 101:
            log.warning("'slowdown' must be in range 0 - 100")
            return
        self._simulation.slowdown = slowdown

    def _handle_redis_job_metadata(self):
        should_exit = True
        try:
            job = get_current_job()
            job.refresh()
            should_exit = "terminated" in job.meta and job.meta["terminated"]
        except NoSuchJobError:
            pass
        if should_exit:
            self._simulation.stop()

    def publish_results(self, endpoint_buffer):
        if not self.is_enabled():
            return
        result_report = endpoint_buffer.generate_result_report()
        results_validator(result_report)

        results = json.dumps(result_report)
        message_size = utf8len(results)
        if message_size > 64000:
            log.error(f"Do not publish message bigger than 64 MB, current message size "
                      f"{message_size / 1000.0} MB.")
            return
        log.debug(f"Publishing {message_size} KB of data via Redis.")

        results = results.encode('utf-8')
        results = compress(results)

        self.redis_db.publish(self.result_channel, results)
        self._handle_redis_job_metadata()

    def write_zip_results(self, zip_results):
        if not self.is_enabled():
            return

        fp = open(zip_results, 'rb')
        zip_data = fp.read()
        fp.close()

        zip_results_key = ZIP_RESULTS_KEY + str(self._simulation_id)
        # Write results to a separate Redis key
        self.redis_db.set(zip_results_key, zip_data)
        # Inform d3a-web that a new zip file is available on this key
        self.redis_db.publish(ZIP_RESULTS_CHANNEL, json.dumps(
            {"job_id": self._simulation_id, "zip_redis_key": zip_results_key}
        ))

    def publish_intermediate_results(self, endpoint_buffer):
        # Should have a different format in the future, hence the code duplication
        self.publish_results(endpoint_buffer)

    def is_enabled(self):
        return hasattr(self, 'pubsub')

    def publish_json(self, channel, data):
        self.redis_db.publish(channel, json.dumps(data))


def publish_job_error_output(job_id, traceback):
    StrictRedis.from_url(REDIS_URL).\
        publish(ERROR_CHANNEL, json.dumps({"job_id": job_id, "errors": traceback}))
