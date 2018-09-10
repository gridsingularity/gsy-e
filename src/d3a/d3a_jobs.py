import logging
from os import environ, getpid
import ast

import pendulum
from redis import StrictRedis
from rq import Connection, Worker, get_current_job
from rq.decorators import job

from d3a.models.config import SimulationConfig
from d3a.models.strategy.const import ConstSettings
from d3a.simulation import Simulation
from d3a.web import start_web
from d3a.util import available_simulation_scenarios
from d3a.util import update_advanced_settings


@job('d3a')
def start(scenario, settings):
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

    advanced_settings = settings.get('advanced_settings', None)
    if advanced_settings is not None:
        update_advanced_settings(ast.literal_eval(advanced_settings))

    config = SimulationConfig(
        duration=pendulum.duration(
            days=1 if 'duration' not in settings else settings['duration'].days
        ),
        slot_length=pendulum.duration(
            seconds=15*60 if 'slot_length' not in settings else settings['slot_length'].seconds
        ),
        tick_length=pendulum.duration(
            seconds=15 if 'tick_length' not in settings else settings['tick_length'].seconds
        ),
        market_count=settings.get('market_count', 4),
        cloud_coverage=settings.get('cloud_coverage', ConstSettings.DEFAULT_PV_POWER_PROFILE),
        market_maker_rate=settings.get('market_maker_rate',
                                       str(ConstSettings.DEFAULT_MARKET_MAKER_RATE)),
        iaa_fee=settings.get('iaa_fee', ConstSettings.INTER_AREA_AGENT_FEE_PERCENTAGE)
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
                            exit_on_finish_wait=pendulum.duration(seconds=10),
                            api_url=api_url,
                            redis_job_id=job.id)

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
