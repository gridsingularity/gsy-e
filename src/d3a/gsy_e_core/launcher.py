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
import sys
import os
import click

from datetime import datetime, timedelta
from redis import StrictRedis
from rq import Queue
from subprocess import Popen
from time import sleep
import platform
from gsy_framework.utils import check_redis_health
from d3a.gsy_e_core.util import get_simulation_queue_name

REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost')
MAX_JOBS = os.environ.get('D3A_MAX_JOBS_PER_POD', 2)


class Launcher:
    def __init__(self, max_jobs=None, max_delay_seconds=2):
        self.redis_connection = StrictRedis.from_url(REDIS_URL, retry_on_timeout=True)
        self.queue = Queue(get_simulation_queue_name(), connection=self.redis_connection)
        self.max_jobs = max_jobs if max_jobs is not None else int(MAX_JOBS)
        self.max_delay = timedelta(seconds=max_delay_seconds)
        python_executable = sys.executable \
            if platform.python_implementation() != "PyPy" \
            else "pypy3"
        self.command = [python_executable, 'src/d3a/gsy_e_core/d3a_jobs.py']
        self.job_array = []

    def run(self):
        self.job_array.append(self._start_worker())
        while True:
            sleep(1)
            if len(self.job_array) < self.max_jobs and self.is_queue_crowded():
                self.job_array.append(self._start_worker())

            self.job_array = [j for j in self.job_array if j.poll() is None]

    def is_queue_crowded(self):
        check_redis_health(redis_db=self.redis_connection)
        enqueued = self.queue.jobs
        if enqueued:
            earliest = min(job.enqueued_at for job in enqueued)
            if datetime.utcnow() - earliest >= self.max_delay:
                return True
        return False

    def _start_worker(self):
        job_environment = os.environ
        job_environment['REDIS_URL'] = REDIS_URL
        return Popen(self.command, env=job_environment)


@click.command()
def main():
    Launcher().run()


if __name__ == '__main__':
    main()
