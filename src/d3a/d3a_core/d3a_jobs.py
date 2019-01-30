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
import logging
from os import environ, getpid
import ast

import pendulum
from redis import StrictRedis
from rq import Connection, Worker, get_current_job
from rq.decorators import job

from d3a.models.config import SimulationConfig
from d3a.models.const import ConstSettings
from d3a.d3a_core.util import available_simulation_scenarios
from d3a.d3a_core.util import update_advanced_settings
from d3a.d3a_core.simulation import run_simulation


@job('d3a')
def start(scenario, settings):
    logging.getLogger().setLevel(logging.ERROR)

    job = get_current_job()
    job.save_meta()

    if settings is None:
        settings = {}

    advanced_settings = settings.get('advanced_settings', None)
    if advanced_settings is not None:
        update_advanced_settings(ast.literal_eval(advanced_settings))

    config = SimulationConfig(
        sim_duration=pendulum.duration(
            days=1 if 'duration' not in settings else settings['duration'].days
        ),
        slot_length=pendulum.duration(
            seconds=15*60 if 'slot_length' not in settings else settings['slot_length'].seconds
        ),
        tick_length=pendulum.duration(
            seconds=15 if 'tick_length' not in settings else settings['tick_length'].seconds
        ),
        market_count=settings.get('market_count', 1),
        cloud_coverage=settings.get('cloud_coverage',
                                    ConstSettings.PVSettings.DEFAULT_POWER_PROFILE),
        pv_user_profile=settings.get('pv_user_profile', None),
        iaa_fee=settings.get('iaa_fee', ConstSettings.IAASettings.FEE_PERCENTAGE)
    )

    if scenario is None:
        scenario_name = "default"
    elif scenario in available_simulation_scenarios:
        scenario_name = scenario
    else:
        scenario_name = 'json_arg'
        config.area = scenario

    kwargs = {"no_export": True, "pricing_scheme": 0}
    run_simulation(setup_module_name=scenario_name,
                   simulation_config=config,
                   slowdown=settings.get('slowdown', 0),
                   redis_job_id=job.id,
                   kwargs=kwargs)


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
