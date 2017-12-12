from datetime import datetime, timedelta

import sys

import os
from redis import StrictRedis
from rq import Queue
from subprocess import Popen
from time import sleep


class Launcher:
    def __init__(self,
                 queue=None,
                 interface="0.0.0.0",
                 port_min=5000,
                 port_max=5009,
                 max_delay_seconds=2):
        self.queue = queue or Queue('d3a', connection=StrictRedis.from_url(
            os.environ.get('REDIS_URL', 'redis://localhost')))
        self.interface = interface
        self.port = port_min
        self.port_max = 5009
        self.max_delay = timedelta(seconds=max_delay_seconds)
        self.command = [sys.executable, 'src/d3a/d3a_jobs.py']

    def run(self):
        self._start_worker()
        while True:
            sleep(1)
            if self.port < self.port_max and self.is_crowded():
                self.port += 1
                self._start_worker()

    def is_crowded(self):
        enqueued = self.queue.jobs
        if enqueued:
            earliest = min(job.enqueued_at for job in enqueued)
            if datetime.now()-earliest >= self.max_delay:
                return True
        return False

    def _start_worker(self):
        Popen(self.command, env={
            'WORKER_INTERFACE': self.interface,
            'WORKER_PORT': str(self.port)
        })


if __name__ == '__main__':
    Launcher().run()
