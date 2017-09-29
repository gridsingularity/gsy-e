import logging
from pendulum.interval import Interval
from rq import get_current_job
from rq.decorators import job

from d3a.models.config import SimulationConfig
from d3a.simulation import Simulation
from d3a.web import start_web


@job('default', timeout='60s')
def start():
    logging.getLogger().setLevel(logging.ERROR)
    interface = "0.0.0.0"
    port = 5000
    api_url = "http://{}:{}/api".format(interface, port)

    job = get_current_job()
    job.meta['api_url'] = api_url
    job.save_meta()

    config = SimulationConfig(
        duration=Interval(hours=12),
        slot_length=Interval(minutes=15),
        tick_length=Interval(seconds=15),
        market_count=4
    )

    simulation = Simulation('default', config, api_url=api_url)
    start_web(interface, port, simulation)
    simulation.run()
