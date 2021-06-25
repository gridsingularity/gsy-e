"""
Copyright 2018 Grid Singularity
This file is part of D3A.
This program is free software: you can redistribute it and/or modify it under the terms of the GNU
General Public License as published by the Free Software Foundation, either version 3 of the
License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without
even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
General Public License for more details.

You should have received a copy of the GNU General Public License along with this program. If not,
see <http://www.gnu.org/licenses/>.
"""
import os

import pytest
from d3a.d3a_core.util import d3a_path, StrategyProfileConfigurationException
from d3a.models.strategy.predefined_load import DefinedLoadStrategy
from d3a_interface.exceptions import D3ADeviceException
from parameterized import parameterized

from tests.test_strategy_load_hours import FakeArea


@parameterized.expand([
    [True, 40, ], [False, 40, ]
])
def test_predefined_load_strategy_rejects_incorrect_rate_parameters(use_mmr, initial_buying_rate):
    user_profile_path = os.path.join(d3a_path, "resources/Solar_Curve_W_sunny.csv")
    load = DefinedLoadStrategy(
        daily_load_profile=user_profile_path,
        initial_buying_rate=initial_buying_rate,
        use_market_maker_rate=use_mmr)
    load.area = FakeArea()
    load.owner = load.area
    with pytest.raises(D3ADeviceException):
        load.event_activate()
    with pytest.raises(D3ADeviceException):
        DefinedLoadStrategy(daily_load_profile=user_profile_path, fit_to_limit=True,
                            energy_rate_increase_per_update=1)
    with pytest.raises(D3ADeviceException):
        DefinedLoadStrategy(daily_load_profile=user_profile_path, fit_to_limit=False,
                            energy_rate_increase_per_update=-1)


def test_strategy_raises_strategy_profile_configuration_exception():
    with pytest.raises(StrategyProfileConfigurationException):
        DefinedLoadStrategy(daily_load_profile_uuid=None, daily_load_profile=None)
