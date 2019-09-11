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
import contextlib
import shutil
import os

from d3a.d3a_core.device_registry import DeviceRegistry
from d3a.d3a_core.util import update_advanced_settings, constsettings_to_dict
from d3a_interface.constants_limits import ConstSettings

"""
before_step(context, step), after_step(context, step)
    These run before and after every step.
    The step passed in is an instance of Step.
before_scenario(context, scenario), after_scenario(context, scenario)
    These run before and after each scenario is run.
    The scenario passed in is an instance of Scenario.
before_feature(context, feature), after_feature(context, feature)
    These run before and after each feature file is exercised.
    The feature passed in is an instance of Feature.
before_tag(context, tag), after_tag(context, tag)
"""

# -- SETUP: Use cfparse as default matcher
# from behave import use_step_matcher
# step_matcher("cfparse")


def before_scenario(context, scenario):
    context.simdir = "./d3a-simulation/integration_tests/"
    os.makedirs(context.simdir, exist_ok=True)
    context.resource_manager = contextlib.ExitStack()
    ConstSettings.GeneralSettings.KEEP_PAST_MARKETS = True


def after_scenario(context, scenario):
    shutil.rmtree(context.simdir)

    update_advanced_settings(context.default_const_settings)
    context.resource_manager.close()
    DeviceRegistry.REGISTRY = {}


def before_all(context):
    context.default_const_settings = constsettings_to_dict()
    context.config.setup_logging()
    ConstSettings.GeneralSettings.KEEP_PAST_MARKETS = True
