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
import traceback
import time
from zlib import compress
from logging import getLogger
from redis import StrictRedis
from redis.exceptions import ConnectionError
from rq import get_current_job
from rq.exceptions import NoSuchJobError

from d3a_interface.results_validator import results_validator  # NOQA
from d3a_interface.constants_limits import HeartBeat
from d3a_interface.utils import RepeatingTimer, get_json_dict_memory_allocation_size
from d3a_interface.exceptions import D3AException


log = getLogger(__name__)


REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost')

ERROR_CHANNEL = "d3a-errors"
RESULTS_CHANNEL = "d3a-results"
ZIP_RESULTS_CHANNEL = "d3a-zip-results"
ZIP_RESULTS_KEY = "d3a-zip-results-key/"


class RedisSimulationCommunication:
    def __init__(self, simulation, simulation_id, live_events):
        if simulation_id is None:
            return
        self._live_events = live_events
        self._simulation_id = simulation_id
        self._simulation = simulation
        self._sub_callback_dict = {
            self._simulation_id + "/stop": self._stop_callback,
            self._simulation_id + "/pause": self._pause_callback,
            self._simulation_id + "/resume": self._resume_callback,
            self._simulation_id + "/live-event": self._live_event_callback,
            self._simulation_id + "/bulk-live-event": self._bulk_live_event_callback}
        self.result_channel = RESULTS_CHANNEL

        try:
            self.redis_db = StrictRedis.from_url(REDIS_URL, retry_on_timeout=True)
            self.pubsub = self.redis_db.pubsub()
            self._subscribe_to_channels()
        except ConnectionError:
            log.error("Redis is not operational, will not use it for communication.")
            del self.pubsub
            return
        self.heartbeat = RepeatingTimer(HeartBeat.RATE, self.heartbeat_tick)
        self.heartbeat.setDaemon(True)
        self.heartbeat.start()

    def _subscribe_to_channels(self):
        self.pubsub.subscribe(**self._sub_callback_dict)
        self.pubsub.run_in_thread(sleep_time=0.1, daemon=True)

    def _generate_redis_response(self, response, simulation_id, is_successful, command_type,
                                 response_params=None):
        if response_params is None:
            response_params = {}
        response_channel = f'{simulation_id}/response/{command_type}'
        if is_successful:
            self.publish_json(
                response_channel,
                {
                    "command": str(command_type), "status": "success",
                    "simulation_id": str(self._simulation_id),
                    "transaction_id": response["transaction_id"],
                    **response_params
                })
        else:
            self.publish_json(
                response_channel,
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
        log.info(f"Simulation with job_id: {self._simulation_id} is stopped.")

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

    def _live_event_callback(self, message):
        data = json.loads(message["data"])
        try:
            self._live_events.add_event(data)
            is_successful = True
        except Exception as e:
            log.error(f"Live event {data} failed. Exception: {e}. "
                      f"Traceback: {traceback.format_exc()}")
            is_successful = False

        self._generate_redis_response(
            data, self._simulation_id, is_successful, 'live-event',
            {"activation_time": self._simulation.progress_info.current_slot_str}
        )

    def _bulk_live_event_callback(self, message):
        data = json.loads(message["data"])
        try:
            for event in data["bulk_event_list"]:
                self._live_events.add_event(event, bulk_event=True)
            is_successful = True
        except Exception as e:
            log.error(f"Live event {data} failed. Exception: {e}. "
                      f"Traceback: {traceback.format_exc()}")
            is_successful = False

        self._generate_redis_response(
            data, self._simulation_id, is_successful, 'bulk-live-event',
            {"activation_time": self._simulation.progress_info.current_slot_str}
        )

    def _handle_redis_job_metadata(self):
        try:
            job = get_current_job()
            job.refresh()
            if "terminated" in job.meta and job.meta["terminated"]:
                log.error(f"Redis job {self._simulation_id} received a stop message via the "
                          f"job.terminated metadata by d3a-web. Stopping the simulation.")
                self._simulation.stop()

        except NoSuchJobError:
            raise D3AException(f"Redis job {self._simulation_id} "
                               f"cannot be found in the Redis job queue. "
                               f"get_current_job failed. Job will de killed.")

    def publish_results(self, endpoint_buffer):
        if not self.is_enabled():
            return
        result_report = endpoint_buffer.generate_result_report()
        results_validator(result_report)

        results = json.dumps(result_report)
        message_size = get_json_dict_memory_allocation_size(result_report)
        if message_size > 64000:
            log.error(f"Do not publish message bigger than 64 MB, current message size "
                      f"{message_size / 1000.0} MB.")
            return
        log.debug(f"Publishing {message_size} KB of data via Redis.")

        results = results.encode('utf-8')
        results = compress(results)

        self._handle_redis_job_metadata()
        self.redis_db.publish(self.result_channel, results)

    def publish_intermediate_results(self, endpoint_buffer):
        # Should have a different format in the future, hence the code duplication
        self.publish_results(endpoint_buffer)

    def is_enabled(self):
        return hasattr(self, 'pubsub')

    def publish_json(self, channel, data):
        self.redis_db.publish(channel, json.dumps(data))

    def heartbeat_tick(self):
        heartbeat_channel = f"{HeartBeat.CHANNEL_NAME}/{self._simulation_id}"
        data = {"time": int(time.time())}
        self.redis_db.publish(heartbeat_channel, json.dumps(data))


def publish_job_error_output(job_id, traceback):
    StrictRedis.from_url(REDIS_URL).\
        publish(ERROR_CHANNEL, json.dumps({"job_id": job_id, "errors": traceback}))
