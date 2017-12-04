import logging
import pendulum.interval as interval
from datetime import timedelta
from os import environ
from rq import Connection, get_current_job, Worker
from rq.decorators import job

from d3a.models.config import SimulationConfig
from d3a.simulation import Simulation
from d3a.web import start_web


@job('d3a')
def start(scenario, settings, message_url_format):
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

    if scenario:
        config.area = scenario

    simulation = Simulation('json_arg' if scenario else 'default',
                            config,
                            slowdown=settings.get('slowdown', 0),
                            exit_on_finish=True,
                            api_url=api_url,
                            message_url=message_url_format.format(job.id))

    start_web(interface, port, simulation)
    simulation.run()


def main():
    with Connection():
        Worker(['d3a']).work()


if __name__ == "__main__":
    main()
