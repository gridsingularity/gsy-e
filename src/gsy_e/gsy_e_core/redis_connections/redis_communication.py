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
from gsy_framework.utils import RepeatingTimer
from redis import StrictRedis
from redis.exceptions import ConnectionError as RedisConnectionError
from rq import get_current_job
from rq.exceptions import NoSuchJobError

import gsy_e.constants
from gsy_e.gsy_e_core.live_events import LiveEventException

log = getLogger(__name__)


REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost")


if TYPE_CHECKING:
    from gsy_e.models.area import Area


class RedisSimulationCommunication:
    """
    Handle Redis connection to the simulation, to receive incoming state change messages or live
    events.
    """
    def __init__(self, simulation_status, simulation_id, live_events, progress_info, area):
        # pylint: disable=too-many-arguments
        self._live_events = live_events
        self._simulation_id = simulation_id if simulation_id is not None else ""
        self._simulation_status = simulation_status
        self._area = area
        self._progress_info = progress_info
        # Lambda is needed here in order to avoid storing the area as a member variable.
        # Instead a closure is used that will capture the area variable in the function scope.
        self._sub_callback_dict = {
            f"{gsy_e.constants.CONFIGURATION_ID}/area-map/": self._calculate_area_map_callback,
            f"{self._simulation_id}/stop": self._stop_callback,
            f"{self._simulation_id}/pause": self._pause_callback,
            f"{self._simulation_id}/resume": self._resume_callback,
            f"{self._simulation_id}/live-event": self._live_event_callback,
            f"{self._simulation_id}/bulk-live-event":
                self._bulk_live_event_callback,
        }

        try:
            self.redis_db = StrictRedis.from_url(REDIS_URL, retry_on_timeout=True)
            pubsub = self.redis_db.pubsub()
            self._subscribe_to_channels(pubsub)
        except RedisConnectionError:
            log.error("Redis is not operational, will not use it for communication.")
            del pubsub
            return
        heartbeat = RepeatingTimer(HeartBeat.RATE, self._heartbeat_tick)
        heartbeat.setDaemon(True)
        heartbeat.start()

    def _subscribe_to_channels(self, pubsub):
        pubsub.subscribe(**self._sub_callback_dict)
        pubsub.run_in_thread(sleep_time=0.1, daemon=True)

    def _generate_redis_response(self, response, is_successful, command_type,
                                 response_params=None):
        if response_params is None:
            response_params = {}
        response_channel = f"{self._simulation_id}/response/{command_type}"

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
        self._publish_json(response_channel, response_json)

    def _calculate_area_map_callback(self, _) -> None:
        """Trigger the calculation of area uuid and name mapping and publish it
        back to a redis response channel"""
        area_mapping = self._area_uuid_name_map_wrapper(self._area)
        response_channel = f"external-myco/{self._simulation_id}/area-map/response/"
        response_dict = {"area_mapping": area_mapping, "event": "area_map_response"}
        self._publish_json(response_channel, response_dict)

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
        self._simulation_status.stop()
        self._generate_redis_response(
            response, self._simulation_status.stopped, "stop"
        )
        log.info("Simulation with job_id: %s is stopped.", self._simulation_id)

    def _pause_callback(self, payload):
        response = json.loads(payload["data"])

        if not self._simulation_status.paused:
            self._simulation_status.toggle_pause()
        self._generate_redis_response(
            response, self._simulation_status.paused, "pause"
        )
        log.info("Simulation with job_id: %s is paused.", self._simulation_id)

    def _resume_callback(self, payload):
        response = json.loads(payload["data"])
        if self._simulation_status.paused:
            self._simulation_status.toggle_pause()
        self._generate_redis_response(
            response, not self._simulation_status.paused, "resume"
        )
        log.info("Simulation with job_id: %s is resumed.", self._simulation_id)

    def _live_event_callback(self, message):
        data = json.loads(message["data"])
        try:
            self._live_events.add_event(data)
            is_successful = True
        except LiveEventException as e:
            log.error("Live event %s failed. Exception: %s. Traceback: %s",
                      data, e, traceback.format_exc())
            is_successful = False

        self._generate_redis_response(
            data, is_successful, "live-event",
            {"activation_time": self._progress_info.current_slot_str}
        )

    def _bulk_live_event_callback(self, message):
        data = json.loads(message["data"])
        try:
            for event in data["bulk_event_list"]:
                self._live_events.add_event(event, bulk_event=True)
            is_successful = True
        except LiveEventException as e:
            log.error("Live event %s failed. Exception: %s. Traceback: %s",
                      data, e, traceback.format_exc())
            is_successful = False

        self._generate_redis_response(
            data, is_successful, "bulk-live-event",
            {"activation_time": self._progress_info.current_slot_str}
        )

    def _handle_redis_job_metadata(self):
        try:
            job = get_current_job()
            job.refresh()
            if job.meta.get("terminated"):
                log.error("Redis job %s received a stop message via the job.terminated metadata "
                          "by gsy-web. Stopping the simulation.", self._simulation_id)
                self._simulation_status.stop()

        except NoSuchJobError as ex:
            raise GSyException(f"Redis job {self._simulation_id} cannot be found in the Redis "
                               "job queue. get_current_job failed. Job will de killed.") from ex

    def _publish_json(self, channel, data):
        self.redis_db.publish(channel, json.dumps(data))

    def _heartbeat_tick(self):
        heartbeat_channel = f"{HeartBeat.CHANNEL_NAME}/{self._simulation_id}"
        data = {"time": int(time.time())}
        self.redis_db.publish(heartbeat_channel, json.dumps(data))


def publish_job_error_output(job_id, traceback_str):
    """Publish error messages to the Redis simulation error message channel."""
    StrictRedis.from_url(REDIS_URL).publish(
        ConstSettings.GeneralSettings.EXCHANGE_ERROR_CHANNEL,
        json.dumps({"job_id": job_id, "errors": traceback_str})
    )
