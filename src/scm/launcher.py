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

import os
import platform
import sys
from subprocess import Popen
from time import sleep

import click

# from gsy_framework.redis_channels import QueueNames
from gsy_framework.utils import check_redis_health
from redis import Redis
from rq import Queue


REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost")
MAX_JOBS = os.environ.get("D3A_MAX_JOBS_PER_POD", 2)
MAX_LIMIT_MEMORY_USAGE_PERCENT = os.environ.get("D3A_MAX_MEM_USAGE_PERCENT", 90)


class Launcher:
    """Launch new simulation jobs after reading from the job queue."""

    def __init__(self, max_jobs=None):
        self.redis_connection = Redis.from_url(REDIS_URL, retry_on_timeout=True)
        self.queue = Queue("scm_job_queue", connection=self.redis_connection)
        self.max_jobs = max_jobs if max_jobs is not None else int(MAX_JOBS)
        python_executable = (
            sys.executable if platform.python_implementation() != "PyPy" else "pypy3"
        )
        self.command = [python_executable, "scm/scm_jobs.py"]
        self.job_array = []

    def run(self):
        """
        Run an endless loop that waits for new jobs to appear in the queue, and starts workers
        in order to execute them.
        """
        self.job_array.append(self._start_worker())
        while True:
            sleep(1)

            if len(self.job_array) < self.max_jobs and self._is_queue_crowded():
                self.job_array.append(self._start_worker())

            self.job_array = [j for j in self.job_array if j.poll() is None]

    def _is_queue_crowded(self):
        check_redis_health(redis_db=self.redis_connection)
        enqueued = self.queue.jobs
        return len(enqueued) > 0

    def _start_worker(self):
        job_environment = os.environ
        job_environment["REDIS_URL"] = REDIS_URL
        return Popen(self.command, env=job_environment)


@click.command()
def main():
    """Entry point of the SCM jobs launch."""
    Launcher().run()


if __name__ == "__main__":
    main()
