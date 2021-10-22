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

from unittest.mock import Mock, MagicMock

import pytest

from d3a.models.area import Area
from d3a.models.market.future import FutureMarkets
from d3a.models.strategy.area_agents.future_agent import FutureAgent
from d3a.models.strategy.area_agents.future_engine import FutureEngine


@pytest.fixture(name="future_agent")
def future_agent_fixture():
    """Return FutureAgent object"""
    area = MagicMock(autospec=Area)
    higher_market = FutureMarkets()
    lower_market = FutureMarkets()
    return FutureAgent(owner=area, higher_market=higher_market, lower_market=lower_market)


class TestFutureAgent:
    """Collects tests for the FutureAgent."""

    @staticmethod
    def test__init__creates_engines_of_correct_type(future_agent):
        """Test whether __init__ creates list of engines off type FutureEngine."""
        for engine in future_agent.engines:
            assert isinstance(engine, FutureEngine)

    @staticmethod
    def test_event_market_cycle_calls_engine_clean_up_buffers(future_agent):
        """Test whether event_market_cycle calls clean_up_buffers of all engines."""
        for engine in future_agent.engines:
            engine.clean_up_order_buffers = Mock()
        future_agent.event_market_cycle()
        for engine in future_agent.engines:
            engine.clean_up_order_buffers.assert_called_once()
