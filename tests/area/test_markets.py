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


from unittest.mock import Mock

import pytest
from d3a_interface.constants_limits import ConstSettings, GlobalConfig
from pendulum import duration

from d3a.d3a_core.device_registry import DeviceRegistry
from d3a.models.area import Area
from d3a.models.strategy.storage import StorageStrategy


class TestMarketRotation:

    @pytest.fixture
    def area_fixture(self):
        DeviceRegistry.REGISTRY = {
            "General Load": (33, 35),
        }
        config = Mock()
        config.slot_length = duration(minutes=15)
        config.tick_length = duration(seconds=15)
        config.ticks_per_slot = 60
        config.start_date = GlobalConfig.start_date
        config.grid_fee_type = ConstSettings.IAASettings.GRID_FEE_TYPE
        config.end_date = GlobalConfig.start_date + duration(days=1)
        config.market_count = 5
        child = Area(name="test_market_area", config=config, strategy=StorageStrategy())
        area = Area(name="parent_area", children=[child], config=config)
        yield area

        DeviceRegistry.REGISTRY = {}

    def test_cycle_markets(self, area_fixture):
        ConstSettings.BalancingSettings.ENABLE_BALANCING_MARKET = True
        area_fixture.activate()
        assert len(area_fixture.all_markets) == 5
        assert len(area_fixture.balancing_markets) == 5
        area_fixture.current_tick = 900
        area_fixture.cycle_markets()
        assert len(area_fixture.past_markets) == 1
        assert len(area_fixture.past_balancing_markets) == 1
        assert len(area_fixture.all_markets) == 5
        assert len(area_fixture.balancing_markets) == 5

    def test_cycle_markets_balancing_market_disabled(self, area_fixture):
        ConstSettings.BalancingSettings.ENABLE_BALANCING_MARKET = False
        area_fixture.activate()
        assert len(area_fixture.balancing_markets) == 0
        area_fixture.current_tick = 900
        area_fixture.cycle_markets()
        assert len(area_fixture.past_balancing_markets) == 0
        assert len(area_fixture.balancing_markets) == 0

    def test_cycle_markets_settlement_markets(self, area_fixture):
        ConstSettings.GeneralSettings.ENABLE_SETTLEMENT_MARKETS = True
        area_fixture.activate()
        max_number_of_settlement_markets = int(
                duration(hours=ConstSettings.GeneralSettings.MAX_AGE_SETTLEMENT_MARKET_HOURS) /
                area_fixture.config.slot_length)
        for cycle_count in range(1, max_number_of_settlement_markets + 2):
            area_fixture.current_tick = area_fixture.config.ticks_per_slot * cycle_count
            area_fixture.cycle_markets()
            assert len(area_fixture.all_markets) == 5
            assert len(area_fixture.past_markets) == 1
            assert len(area_fixture.settlement_markets) == min(cycle_count,
                                                               max_number_of_settlement_markets)
