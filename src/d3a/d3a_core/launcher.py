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


REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost')


class Launcher:
    def __init__(self,
                 queue=None,
                 max_jobs=4,
                 max_delay_seconds=2):
        self.queue = queue or Queue('d3a', connection=StrictRedis.from_url(REDIS_URL))
        self.max_jobs = max_jobs
        self.max_delay = timedelta(seconds=max_delay_seconds)
        self.command = [sys.executable, 'src/d3a/d3a_core/d3a_jobs.py']
        self.job_array = []

    def run(self):
        self.job_array.append(self._start_worker())
        while True:
            sleep(1)
            if len(self.job_array) <= self.max_jobs and self.is_crowded():
                self._start_worker()

            self.job_array = [j for j in self.job_array if j.poll() is None]

    def is_crowded(self):
        enqueued = self.queue.jobs
        if enqueued:
            earliest = min(job.enqueued_at for job in enqueued)
            if datetime.now()-earliest >= self.max_delay:
                return True
        return False

    def _start_worker(self):
        return Popen(self.command, env={'REDIS_URL': REDIS_URL})


@click.command()
def main():
    Launcher().run()


if __name__ == '__main__':
    main()
