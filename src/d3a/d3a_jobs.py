import logging
import pendulum.interval as interval
from datetime import timedelta
from os import environ
from rq import Connection, get_current_job, Worker
from rq.decorators import job

from d3a.models.config import SimulationConfig
from d3a.simulation import Simulation
from d3a.web import start_web


@job('default')
def start(scenario, settings):
    logging.getLogger().setLevel(logging.ERROR)
    interface = environ.get('WORKER_INTERFACE', "0.0.0.0")
    port = int(environ.get('WORKER_PORT', 5000))
    api_url = "http://{}:{}/api".format(interface, port)

    job = get_current_job()
    job.meta['api_url'] = api_url
    job.save_meta()

    if settings is None:
        settings = {}

    config = SimulationConfig(
        duration=interval.instance(settings.get('duration', timedelta(days=1))),
        slot_length=interval.instance(settings.get('slot_length', timedelta(minutes=15))),
        tick_length=interval.instance(settings.get('tick_length', timedelta(seconds=1))),
        market_count=settings.get('market_count', 4)
    )

    simulation = Simulation('default', config, api_url=api_url,
                            slowdown=settings.get('slowdown', 0))

    start_web(interface, port, simulation)
    simulation.run()


def main():
    with Connection():
        Worker(['default']).work()


if __name__ == "__main__":
    main()
