"""
Copyright 2018 Grid Singularity
This file is part of Grid Singularity Exchange.

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
import json
import os
import time
import traceback
from logging import getLogger
from typing import Dict, TYPE_CHECKING, Optional

from gsy_framework.constants_limits import HeartBeat, ConstSettings
from gsy_framework.exceptions import GSyException
from gsy_framework.results_validator import results_validator  # NOQA
from gsy_framework.utils import RepeatingTimer
from redis import StrictRedis
from redis.exceptions import ConnectionError
from rq import get_current_job
from rq.exceptions import NoSuchJobError

import gsy_e.constants

log = getLogger(__name__)


REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost')


if TYPE_CHECKING:
    from gsy_e.models.area import Area


class RedisSimulationCommunication:
    def __init__(self, simulation, simulation_id, live_events):
        self._live_events = live_events
        self._simulation_id = simulation_id if simulation_id is not None else ""
        self._configuration_id = gsy_e.constants.CONFIGURATION_ID
        self._simulation = simulation
        self._sub_callback_dict = {
            f"{self._configuration_id}/area-map/": self._area_map_callback,
            f"{self._simulation_id}/stop": self._stop_callback,
            f"{self._simulation_id}/pause": self._pause_callback,
            f"{self._simulation_id}/resume": self._resume_callback,
            f"{self._simulation_id}/live-event": self._live_event_callback,
            f"{self._simulation_id}/bulk-live-event":
                self._bulk_live_event_callback,
        }

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

        response_json = {
            "command": str(command_type),
            "simulation_id": str(self._simulation_id),
            "transaction_id": response["transaction_id"],
        }
        if is_successful:
            response_json.update(
                {
                    "status": "success", **response_params
                })
        else:
            response_json.update(
                {
                    "status": "error",
                    "error_message": f"Error when handling simulation {command_type}."
                })
        self.publish_json(response_channel, response_json)

    def _area_map_callback(self, payload: Dict) -> None:
        """Trigger the calculation of area uuid and name mapping and publish it
        back to a redis response channel"""
        area_mapping = self._area_uuid_name_map_wrapper(self._simulation.area)
        response_channel = f"external-myco/{self._simulation_id}/area-map/response/"
        response_dict = {"area_mapping": area_mapping, "event": "area_map_response"}
        self.publish_json(response_channel, response_dict)

    @classmethod
    def _area_uuid_name_map_wrapper(
            cls, area: "Area", area_mapping: Optional[dict] = None) -> Dict:
        """Recursive method to populate area uuid and name map for area object"""
        area_mapping = area_mapping or {}
        area_mapping[area.uuid] = area.name
        for child in area.children:
            area_mapping = RedisSimulationCommunication._area_uuid_name_map_wrapper(
                child, area_mapping)
        return area_mapping

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
            if job.meta.get("terminated"):
                log.error(f"Redis job {self._simulation_id} received a stop "
                          "message via the job.terminated metadata by gsy-web. "
                          "Stopping the simulation.")
                self._simulation.stop()

        except NoSuchJobError:
            raise GSyException(f"Redis job {self._simulation_id} "
                               f"cannot be found in the Redis job queue. "
                               f"get_current_job failed. Job will de killed.")

    def publish_json(self, channel, data):
        self.redis_db.publish(channel, json.dumps(data))

    def heartbeat_tick(self):
        heartbeat_channel = f"{HeartBeat.CHANNEL_NAME}/{self._simulation_id}"
        data = {"time": int(time.time())}
        self.redis_db.publish(heartbeat_channel, json.dumps(data))


def publish_job_error_output(job_id, traceback):
    StrictRedis.from_url(REDIS_URL).\
        publish(ConstSettings.GeneralSettings.EXCHANGE_ERROR_CHANNEL,
                json.dumps({"job_id": job_id, "errors": traceback}))
