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
from os import environ, getpid
from pendulum import now
from redis import StrictRedis
from rq import Connection, Worker, get_current_job
from rq.decorators import job
from d3a.d3a_core.util import get_simulation_queue_name


@job('d3a')
def start(scenario, settings, events, aggregator_device_mapping, saved_state):
    from d3a.d3a_core.rq_job_handler import launch_simulation_from_rq_job
    job = get_current_job()
    job.save_meta()
    launch_simulation_from_rq_job(scenario, settings, events, aggregator_device_mapping,
                                  saved_state, job.id)


def main():
    with Connection(StrictRedis.from_url(environ.get('REDIS_URL', 'redis://localhost'),
                                         retry_on_timeout=True)):
        Worker(
            [get_simulation_queue_name()],
            name=f'simulation.{getpid()}.{now().timestamp()}', log_job_description=False
        ).work(max_jobs=1, burst=True)


if __name__ == "__main__":
    main()
