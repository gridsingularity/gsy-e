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
import uuid
from unittest.mock import Mock, MagicMock

import pytest
from pendulum import today, duration
from d3a_interface.constants_limits import GlobalConfig

from d3a.constants import TIME_ZONE, FutureTemplateStrategiesConstants
from d3a.models.market.future import FutureMarkets
from d3a.models.strategy.future.strategy import FutureMarketStrategy
from d3a.models.strategy.load_hours import LoadHoursStrategy
from d3a.models.strategy.pv import PVStrategy


class TestFutureMarketStrategy:

    def setup_method(self):
        self.future_strategy = FutureMarketStrategy(10, 50, 50, 20)
        self.time_slot = today(tz=TIME_ZONE).at(hour=12, minute=0, second=0)
        self.area_mock = Mock()
        self.area_mock.name = "test_name"
        self.area_mock.uuid = str(uuid.uuid4())
        self.future_markets = MagicMock(spec=FutureMarkets)
        self.future_markets.market_time_slots = [self.time_slot]
        self.future_markets.id = str(uuid.uuid4())

    def _setup_strategy_fixture(self, future_strategy_fixture):
        future_strategy_fixture.owner = self.area_mock
        future_strategy_fixture.update_bid_rates = Mock()
        future_strategy_fixture.update_offer_rates = Mock()
        future_strategy_fixture.area = Mock()
        future_strategy_fixture.area.future_markets = self.future_markets
        future_strategy_fixture.area.current_tick = 0
        future_strategy_fixture.area.config = Mock()
        future_strategy_fixture.area.config.ticks_per_slot = 60
        future_strategy_fixture.area.config.tick_length = duration(seconds=15)

    @pytest.mark.parametrize(
        "future_strategy_fixture", [LoadHoursStrategy(100), PVStrategy()])
    def test_event_market_cycle_posts_bids_and_offers(self, future_strategy_fixture):
        self._setup_strategy_fixture(future_strategy_fixture)
        if isinstance(future_strategy_fixture, LoadHoursStrategy):
            future_strategy_fixture.state.set_desired_energy(1234.0, self.time_slot)
            self.future_strategy.event_market_cycle(future_strategy_fixture)
            self.future_markets.bid.assert_called_once_with(
                10.0, 1.234, self.area_mock.name, original_price=10.0,
                buyer_origin=self.area_mock.name, buyer_origin_id=self.area_mock.uuid,
                buyer_id=self.area_mock.uuid, attributes=None, requirements=None,
                time_slot=self.time_slot
            )
        if isinstance(future_strategy_fixture, PVStrategy):
            future_strategy_fixture.state.set_available_energy(321.3, self.time_slot)
            self.future_strategy.event_market_cycle(future_strategy_fixture)
            self.future_markets.offer.assert_called_once_with(
                price=50.0, energy=321.3, seller=self.area_mock.name,
                seller_origin=self.area_mock.name,
                seller_origin_id=self.area_mock.uuid, seller_id=self.area_mock.uuid,
                time_slot=self.time_slot
            )

    @pytest.mark.parametrize(
        "future_strategy_fixture", [LoadHoursStrategy(100), PVStrategy()])
    def test_event_tick_updates_bids_and_offers(self, future_strategy_fixture):
        self._setup_strategy_fixture(future_strategy_fixture)
        future_strategy_fixture.are_bids_posted = MagicMock(return_value=True)
        future_strategy_fixture.are_offers_posted = MagicMock(return_value=True)

        if isinstance(future_strategy_fixture, LoadHoursStrategy):
            future_strategy_fixture.state.set_desired_energy(2000.0, self.time_slot)
        if isinstance(future_strategy_fixture, PVStrategy):
            future_strategy_fixture.state.set_available_energy(300.0, self.time_slot)
        future_strategy_fixture.area.current_tick = 0
        future_strategy_fixture.area.config = Mock()
        future_strategy_fixture.area.config.tick_length = duration(seconds=15)
        self.future_strategy.event_market_cycle(future_strategy_fixture)

        ticks_for_update = FutureTemplateStrategiesConstants.UPDATE_INTERVAL_MIN * 60 / 15
        future_strategy_fixture.area.current_tick = ticks_for_update - 1
        self.future_markets.bid.reset_mock()
        self.future_markets.offer.reset_mock()

        future_strategy_fixture.area.current_tick = ticks_for_update - 1
        self.future_strategy.event_tick(future_strategy_fixture)
        future_strategy_fixture.area.current_tick = ticks_for_update
        self.future_strategy.event_tick(future_strategy_fixture)
        if isinstance(future_strategy_fixture, LoadHoursStrategy):
            energy_rate_range = 50 - 10
            number_of_updates = (GlobalConfig.FUTURE_MARKET_DURATION_HOURS * 60 * 60 /
                                 self.future_strategy._bid_updater.update_interval.seconds - 1)
            energy_rate = energy_rate_range / number_of_updates

            future_strategy_fixture.update_bid_rates.assert_called_once_with(
                self.future_markets, 10 + energy_rate)
        if isinstance(future_strategy_fixture, PVStrategy):
            energy_rate_range = 50 - 20
            number_of_updates = (GlobalConfig.FUTURE_MARKET_DURATION_HOURS * 60 * 60 /
                                 self.future_strategy._offer_updater.update_interval.seconds - 1)
            energy_rate = energy_rate_range / number_of_updates
            future_strategy_fixture.update_offer_rates.assert_called_once_with(
                self.future_markets, 50 - energy_rate)
