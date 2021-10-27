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

from unittest.mock import MagicMock

import pytest
from d3a_interface.constants_limits import ConstSettings
from d3a_interface.enums import SpotMarketTypeEnum

from d3a.models.area import Area
from d3a.models.area.event_dispatcher import AreaDispatcher
from d3a.models.market import Market
from d3a.models.market.future import FutureMarkets
from d3a.models.market.market_structures import AvailableMarketTypes
from d3a.models.strategy.area_agents.balancing_agent import BalancingAgent
from d3a.models.strategy.area_agents.future_agent import FutureAgent
from d3a.models.strategy.area_agents.inter_area_agent import InterAreaAgent
from d3a.models.strategy.area_agents.one_sided_agent import OneSidedAgent
from d3a.models.strategy.area_agents.settlement_agent import SettlementAgent
from d3a.models.strategy.area_agents.two_sided_agent import TwoSidedAgent

LOWER_MARKET_MOCK = MagicMock(autospec=Market)
HIGHER_MARKET_MOCK = MagicMock(autospec=Market)


@pytest.fixture(name="area_dispatcher")
def area_dispatcher_fixture():
    area = Area("name")
    area.parent = Area("parent")
    area.children = [Area("child1"), Area("child2")]
    return AreaDispatcher(area)


class TestAreaDispatcher:

    @staticmethod
    @pytest.mark.parametrize("market_type, matching_type, expected_agent_type", [
        [AvailableMarketTypes.SPOT, SpotMarketTypeEnum.ONE_SIDED.value, OneSidedAgent],
        [AvailableMarketTypes.SPOT, SpotMarketTypeEnum.TWO_SIDED.value, TwoSidedAgent],
        [AvailableMarketTypes.SETTLEMENT, SpotMarketTypeEnum.TWO_SIDED.value, SettlementAgent],
        [AvailableMarketTypes.BALANCING, SpotMarketTypeEnum.TWO_SIDED.value, BalancingAgent],
        [AvailableMarketTypes.FUTURE, SpotMarketTypeEnum.TWO_SIDED.value, FutureAgent]
    ])
    def test_create_agent_object_returns_correct_opjects(market_type: AvailableMarketTypes,
                                                         matching_type: SpotMarketTypeEnum,
                                                         expected_agent_type: InterAreaAgent,
                                                         area_dispatcher):
        """"""
        original_matching_type = ConstSettings.IAASettings.MARKET_TYPE
        ConstSettings.IAASettings.MARKET_TYPE = matching_type
        agent = area_dispatcher._create_agent_object(area_dispatcher.area, HIGHER_MARKET_MOCK,
                                                     LOWER_MARKET_MOCK, market_type)
        assert isinstance(agent, expected_agent_type)
        assert agent.higher_market == HIGHER_MARKET_MOCK
        assert agent.lower_market == LOWER_MARKET_MOCK
        assert agent.owner == area_dispatcher.area

        ConstSettings.IAASettings.MARKET_TYPE = original_matching_type

    def test_create_area_agents_for_future_markets(self, area_dispatcher):
        area_dispatcher.area.parent._markets.future_markets = MagicMock(autospec=FutureMarkets)
        area_dispatcher.create_area_agents_for_future_markets(LOWER_MARKET_MOCK)
        assert isinstance(area_dispatcher.future_agent, FutureAgent)
