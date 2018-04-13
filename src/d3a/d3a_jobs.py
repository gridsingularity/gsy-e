import logging
from datetime import timedelta
from os import environ, getpid

import pendulum
import pendulum.interval as interval
from redis import StrictRedis
from rq import Connection, Worker, get_current_job
from rq.decorators import job

from d3a.models.config import SimulationConfig
from d3a.simulation import Simulation
from d3a.web import start_web
from d3a.util import available_simulation_scenarios


@job('d3a')
def start(scenario, settings, message_url_format):
    logging.getLogger().setLevel(logging.ERROR)
    interface = environ.get('WORKER_INTERFACE', "0.0.0.0")
    port = int(environ.get('WORKER_PORT', 5000))
    api_host = environ.get('WORKER_HOST', interface)
    api_url = "http://{}:{}/api".format(api_host, port)

    job = get_current_job()
    job.meta['api_url'] = api_url
    job.save_meta()

    if settings is None:
        settings = {}

    config = SimulationConfig(
        duration=interval.instance(settings.get('duration', timedelta(days=1))),
        slot_length=interval.instance(settings.get('slot_length', timedelta(minutes=15))),
        tick_length=interval.instance(settings.get('tick_length', timedelta(seconds=15))),
        market_count=settings.get('market_count', 4)
    )

    if scenario is None:
        scenario_name = "default"
    elif scenario in available_simulation_scenarios:
        scenario_name = scenario
    else:
        scenario_name = 'json_arg'
        config.area = scenario

    simulation = Simulation(scenario_name,
                            config,
                            slowdown=settings.get('slowdown', 0),
                            exit_on_finish=True,
                            exit_on_finish_wait=interval.instance(timedelta(seconds=10)),
                            api_url=api_url,
                            message_url=message_url_format.format(job.id))

    start_web(interface, port, simulation)
    simulation.run()


@job('d3a')
def get_simulation_scenarios():
    return available_simulation_scenarios


def main():
    with Connection(StrictRedis.from_url(environ.get('REDIS_URL', 'redis://localhost'))):
        Worker(
            ['d3a'],
            name='simulation.{}.{:%s}'.format(getpid(), pendulum.now())
        ).work()


if __name__ == "__main__":
    main()
