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


from unittest.mock import Mock, patch

import pytest
from gsy_framework.constants_limits import ConstSettings, TIME_ZONE, GlobalConfig
from pendulum import duration, today

import gsy_e
from gsy_e.gsy_e_core.device_registry import DeviceRegistry
from gsy_e.models.area import Area
from gsy_e.models.strategy.storage import StorageStrategy


class TestMarketRotation:

    @staticmethod
    @pytest.fixture
    def area_fixture():
        """Fixture for an area object."""
        original_future_markets = ConstSettings.FutureMarketSettings.FUTURE_MARKET_DURATION_HOURS
        ConstSettings.FutureMarketSettings.FUTURE_MARKET_DURATION_HOURS = 24
        original_registry = DeviceRegistry.REGISTRY
        DeviceRegistry.REGISTRY = {
            "General Load": (33, 35),
        }
        config = Mock()
        config.slot_length = duration(minutes=15)
        config.tick_length = duration(seconds=15)
        config.ticks_per_slot = 60
        config.start_date = today(tz=TIME_ZONE)
        config.grid_fee_type = ConstSettings.MASettings.GRID_FEE_TYPE
        config.end_date = config.start_date + duration(days=1)
        child = Area(name="test_market_area", config=config, strategy=StorageStrategy())
        area = Area(name="parent_area", children=[child], config=config)
        ConstSettings.BalancingSettings.ENABLE_BALANCING_MARKET = False
        ConstSettings.SettlementMarketSettings.ENABLE_SETTLEMENT_MARKETS = False
        gsy_e.constants.RETAIN_PAST_MARKET_STRATEGIES_STATE = False

        yield area

        ConstSettings.FutureMarketSettings.FUTURE_MARKET_DURATION_HOURS = original_future_markets
        DeviceRegistry.REGISTRY = original_registry
        ConstSettings.BalancingSettings.ENABLE_BALANCING_MARKET = False
        ConstSettings.SettlementMarketSettings.ENABLE_SETTLEMENT_MARKETS = False
        gsy_e.constants.RETAIN_PAST_MARKET_STRATEGIES_STATE = False

    @staticmethod
    def test_market_rotation_is_successful(area_fixture):
        ConstSettings.BalancingSettings.ENABLE_BALANCING_MARKET = True
        area_fixture.activate()
        assert len(area_fixture.all_markets) == 1
        ticks_per_slot = area_fixture.config.slot_length / area_fixture.config.tick_length
        area_fixture.current_tick = ticks_per_slot
        area_fixture.cycle_markets()
        assert len(area_fixture.past_markets) == 1
        assert len(area_fixture.all_markets) == 1
        assert len(area_fixture.balancing_markets) == 1

        area_fixture.current_tick = ticks_per_slot * 2
        area_fixture.cycle_markets()
        # if RETAIN_PAST_MARKET_STRATEGIES_STATE == False, only one past market is kep in memory
        assert len(area_fixture.past_markets) == 1
        assert len(area_fixture.all_markets) == 1

    @staticmethod
    @patch("gsy_e.constants.RETAIN_PAST_MARKET_STRATEGIES_STATE", True)
    def test_market_rotation_is_successful_keep_past_markets(area_fixture):
        area_fixture.activate()
        assert len(area_fixture.all_markets) == 1
        ticks_per_slot = area_fixture.config.slot_length / area_fixture.config.tick_length
        area_fixture.current_tick = ticks_per_slot
        area_fixture.cycle_markets()
        # The expected future market count is market slots for the whole simulation duration
        # -2 to not take into account the first 2 market slots due to the cycle_markets call
        expected_number_of_future_markets = (
                GlobalConfig.sim_duration / area_fixture.config.slot_length - 2)
        assert len(area_fixture.past_markets) == 1
        assert len(area_fixture.all_markets) == 1
        assert len(area_fixture.future_market_time_slots) == expected_number_of_future_markets

        area_fixture.current_tick = ticks_per_slot * 2
        area_fixture.cycle_markets()
        assert len(area_fixture.past_markets) == 2
        assert len(area_fixture.all_markets) == 1
        # The cycle_markets decreases by one the count of expected future markets
        assert len(area_fixture.future_market_time_slots) == expected_number_of_future_markets - 1

    @staticmethod
    @patch("gsy_framework.constants_limits.ConstSettings.BalancingSettings."
           "ENABLE_BALANCING_MARKET", True)
    def test_balancing_market_rotation_is_successful(area_fixture):
        area_fixture.activate()
        assert len(area_fixture.balancing_markets) == 1
        ticks_per_slot = area_fixture.config.slot_length / area_fixture.config.tick_length
        area_fixture.current_tick = ticks_per_slot
        area_fixture.cycle_markets()
        assert len(area_fixture.past_balancing_markets) == 1
        assert len(area_fixture.balancing_markets) == 1

        area_fixture.current_tick = ticks_per_slot * 2
        area_fixture.cycle_markets()
        assert len(area_fixture.past_balancing_markets) == 1
        assert len(area_fixture.balancing_markets) == 1

    @staticmethod
    @patch("gsy_framework.constants_limits.ConstSettings.SettlementMarketSettings."
           "ENABLE_SETTLEMENT_MARKETS", True)
    def test_settlement_market_rotation_is_successful(area_fixture):
        """
        #slot   #markets #past_markets #settlement_markets #past_settlement_markets
        1            1         1             1                   0
        2            1         2             2                   0
        3            1         3             3                   0
        4            1         4             4                   0
        5            1         4             4                   1
        6            1         4             4                   1

        """
        expected_market_cycles = {
            area_fixture.config.start_date: [1, 1, 1, 0],
            area_fixture.config.start_date + 1 * area_fixture.config.slot_length: [1, 2, 2, 0],
            area_fixture.config.start_date + 2 * area_fixture.config.slot_length: [1, 3, 3, 0],
            area_fixture.config.start_date + 3 * area_fixture.config.slot_length: [1, 4, 4, 0],
            area_fixture.config.start_date + 4 * area_fixture.config.slot_length: [1, 4, 4, 1],
            area_fixture.config.start_date + 5 * area_fixture.config.slot_length: [1, 4, 4, 1],
        }

        area_fixture.activate()
        ticks_per_slot = area_fixture.config.slot_length / area_fixture.config.tick_length

        current_slot_number = 1
        for expected_counts in expected_market_cycles.values():
            area_fixture.current_tick = ticks_per_slot * current_slot_number
            area_fixture.cycle_markets()

            assert len(area_fixture.all_markets) == expected_counts[0]
            assert len(area_fixture.past_markets) == expected_counts[1]
            assert len(area_fixture.settlement_markets) == expected_counts[2]
            assert len(area_fixture.past_settlement_markets) == expected_counts[3]

            current_slot_number += 1
