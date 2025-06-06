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

import logging
from os import environ, getpid

from gsy_framework.data_serializer import DataSerializer
from gsy_framework.redis_channels import QueueNames
from pendulum import now
from redis import Redis
from rq import Worker, get_current_job
from rq.decorators import job

logger = logging.getLogger()

redis_conn = Redis.from_url(environ.get("REDIS_URL", "redis://localhost"), retry_on_timeout=True)


@job("exchange", connection=redis_conn)
def start(payload):
    """Start a simulation with a Redis job."""
    # pylint: disable-next=import-outside-toplevel
    from gsy_e.gsy_e_core.rq_job_handler import launch_simulation_from_rq_job

    current_job = get_current_job()
    current_job.save_meta()
    payload = DataSerializer.decompress_and_decode(payload)
    launch_simulation_from_rq_job(**payload, job_id=current_job.id)


def main():
    """Main entrypoint for running the exchange jobs."""
    worker = Worker(
        [QueueNames().gsy_e_queue_name],
        connection=redis_conn,
        name=f"simulation.{getpid()}.{now().timestamp()}",
        log_job_description=False,
    )
    try:
        worker.work(max_jobs=1, burst=True, logging_level="ERROR")
    except Exception as ex:  # pylint: disable=broad-except
        logger.exception(ex)
        worker.kill_horse()
        worker.wait_for_horse()


if __name__ == "__main__":
    main()
