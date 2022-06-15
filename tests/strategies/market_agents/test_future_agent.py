"""
Copyright 2018 Grid Singularity
This file is part of Grid Singularity Exchange.

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

from typing import Generator
from unittest.mock import MagicMock

import pytest
from gsy_framework.constants_limits import ConstSettings

from gsy_e.models.area import Area
from gsy_e.models.market.future import FutureMarkets
from gsy_e.models.strategy.market_agents.future_agent import FutureAgent
from gsy_e.models.strategy.market_agents.future_engine import FutureEngine


@pytest.fixture(name="future_agent")
def future_agent_fixture() -> Generator[FutureAgent, None, None]:
    """Return FutureAgent object"""
    original_future_markets_duration = (
        ConstSettings.FutureMarketSettings.FUTURE_MARKET_DURATION_HOURS)
    ConstSettings.FutureMarketSettings.FUTURE_MARKET_DURATION_HOURS = 24
    area = MagicMock(autospec=Area)
    higher_market = FutureMarkets()
    lower_market = FutureMarkets()
    yield FutureAgent(owner=area, higher_market=higher_market, lower_market=lower_market)
    ConstSettings.FutureMarketSettings.FUTURE_MARKET_DURATION_HOURS = (
        original_future_markets_duration)


class TestFutureAgent:
    """Collects tests for the FutureAgent."""

    @staticmethod
    def test__init__creates_engines_of_correct_type(future_agent: FutureAgent) -> None:
        """Test whether __init__ creates list of engines off type FutureEngine."""
        for engine in future_agent.engines:
            assert isinstance(engine, FutureEngine)
