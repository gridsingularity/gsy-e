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
from typing import TYPE_CHECKING
from unittest.mock import Mock, MagicMock

import pytest
from gsy_framework.constants_limits import GlobalConfig, ConstSettings, TIME_ZONE
from gsy_framework.data_classes import TraderDetails
from pendulum import today, duration

from gsy_e.constants import FutureTemplateStrategiesConstants
from gsy_e.models.market.future import FutureMarkets
from gsy_e.models.strategy.future.strategy import FutureMarketStrategy
from gsy_e.models.strategy.load_hours import LoadHoursStrategy
from gsy_e.models.strategy.pv import PVStrategy
from gsy_e.models.strategy.storage import StorageStrategy

if TYPE_CHECKING:
    from gsy_e.models.strategy import BaseStrategy


class TestFutureMarketStrategy:
    """Test the FutureMarketStrategy class."""

    # pylint: disable = attribute-defined-outside-init, too-many-instance-attributes

    def setup_method(self) -> None:
        """Preparation for the tests execution"""
        self._original_future_markets_duration = (
            ConstSettings.FutureMarketSettings.FUTURE_MARKET_DURATION_HOURS
        )
        ConstSettings.FutureMarketSettings.FUTURE_MARKET_DURATION_HOURS = 24
        self.time_slot = today(tz=TIME_ZONE).at(hour=12, minute=0, second=0)
        self.area_mock = Mock()
        self.area_mock.name = "test_name"
        self.area_mock.uuid = str(uuid.uuid4())
        GlobalConfig.end_date = GlobalConfig.start_date + GlobalConfig.sim_duration
        self.area_mock.config = GlobalConfig
        self.future_markets = MagicMock(spec=FutureMarkets)
        self.future_markets.market_time_slots = [self.time_slot]
        self.future_markets.id = str(uuid.uuid4())
        self._original_initial_buying_rate = FutureTemplateStrategiesConstants.INITIAL_BUYING_RATE
        self._original_final_buying_rate = FutureTemplateStrategiesConstants.FINAL_BUYING_RATE
        self._original_initial_selling_rate = (
            FutureTemplateStrategiesConstants.INITIAL_SELLING_RATE
        )
        self._original_final_selling_rate = FutureTemplateStrategiesConstants.FINAL_SELLING_RATE

    def teardown_method(self) -> None:
        """Test cleanup"""
        ConstSettings.FutureMarketSettings.FUTURE_MARKET_DURATION_HOURS = (
            self._original_future_markets_duration
        )
        FutureTemplateStrategiesConstants.INITIAL_BUYING_RATE = self._original_initial_buying_rate
        FutureTemplateStrategiesConstants.FINAL_BUYING_RATE = self._original_final_buying_rate
        FutureTemplateStrategiesConstants.INITIAL_SELLING_RATE = (
            self._original_initial_selling_rate
        )
        FutureTemplateStrategiesConstants.FINAL_SELLING_RATE = self._original_final_selling_rate

    def _setup_strategy_fixture(self, future_strategy_fixture: "BaseStrategy") -> None:
        future_strategy_fixture.owner = self.area_mock
        future_strategy_fixture.update_bid_rates = Mock()
        future_strategy_fixture.update_offer_rates = Mock()
        future_strategy_fixture.area = Mock()
        future_strategy_fixture.area.future_markets = self.future_markets
        future_strategy_fixture.area.current_tick = 0
        future_strategy_fixture.area.config = GlobalConfig
        future_strategy_fixture.area.config.tick_length = duration(seconds=15)

    def test_event_market_cycle_posts_bids_load(self) -> None:
        """Validate that market cycle event posts bids and offers for the load strategy"""
        load_strategy_fixture = LoadHoursStrategy(100)
        future_strategy = FutureMarketStrategy(load_strategy_fixture.asset_type, 10, 50, 50, 20)
        self._setup_strategy_fixture(load_strategy_fixture)
        load_strategy_fixture.state.set_desired_energy(1234.0, self.time_slot)
        future_strategy.event_market_cycle(load_strategy_fixture)
        self.future_markets.bid.assert_called_once_with(
            10.0 * 1.234,
            1.234,
            TraderDetails(
                self.area_mock.name, self.area_mock.uuid, self.area_mock.name, self.area_mock.uuid
            ),
            original_price=10.0 * 1.234,
            time_slot=self.time_slot,
        )

    def test_event_market_cycle_posts_offers_pv(self) -> None:
        """Validate that market cycle event posts bids and offers for the pv strategy"""
        pv_strategy_fixture = PVStrategy()
        future_strategy = FutureMarketStrategy(pv_strategy_fixture.asset_type, 10, 50, 50, 20)
        self._setup_strategy_fixture(pv_strategy_fixture)
        pv_strategy_fixture.state.set_available_energy(321.3, self.time_slot)
        future_strategy.event_market_cycle(pv_strategy_fixture)
        self.future_markets.offer.assert_called_once_with(
            price=50.0 * 321.3,
            energy=321.3,
            seller=TraderDetails(
                self.area_mock.name, self.area_mock.uuid, self.area_mock.name, self.area_mock.uuid
            ),
            time_slot=self.time_slot,
        )

    def test_event_market_cycle_posts_bids_and_offers_storage(self) -> None:
        """Validate that market cycle event posts bids and offers for the pv strategy"""
        storage_strategy_fixture = StorageStrategy()
        future_strategy = FutureMarketStrategy(storage_strategy_fixture.asset_type, 10, 50, 50, 20)
        self._setup_strategy_fixture(storage_strategy_fixture)
        storage_strategy_fixture.state.activate(duration(minutes=15), self.time_slot)
        storage_strategy_fixture.state.offered_sell_kWh[self.time_slot] = 0.0
        storage_strategy_fixture.state.offered_buy_kWh[self.time_slot] = 0.0
        storage_strategy_fixture.state.pledged_sell_kWh[self.time_slot] = 0.0
        storage_strategy_fixture.state.pledged_buy_kWh[self.time_slot] = 0.0
        storage_strategy_fixture.state.get_available_energy_to_buy_kWh = Mock(return_value=3)
        storage_strategy_fixture.state.get_available_energy_to_sell_kWh = Mock(return_value=2)
        storage_strategy_fixture.state.register_energy_from_posted_offer = Mock()
        storage_strategy_fixture.state.register_energy_from_posted_bid = Mock()
        future_strategy.event_market_cycle(storage_strategy_fixture)
        self.future_markets.offer.assert_called_once_with(
            price=50.0 * 2,
            energy=2,
            seller=TraderDetails(
                self.area_mock.name, self.area_mock.uuid, self.area_mock.name, self.area_mock.uuid
            ),
            time_slot=self.time_slot,
        )
        storage_strategy_fixture.state.register_energy_from_posted_offer.assert_called_once()

        self.future_markets.bid.assert_called_once_with(
            10.0 * 3,
            3,
            TraderDetails(
                self.area_mock.name, self.area_mock.uuid, self.area_mock.name, self.area_mock.uuid
            ),
            original_price=10.0 * 3,
            time_slot=self.time_slot,
        )

        storage_strategy_fixture.state.register_energy_from_posted_bid.assert_called_once()

    @pytest.mark.parametrize(
        "future_strategy_fixture",
        [LoadHoursStrategy(100), PVStrategy(), StorageStrategy(initial_soc=50)],
    )
    def test_event_tick_updates_bids_and_offers(
        self, future_strategy_fixture: "BaseStrategy"
    ) -> None:
        """Validate that tick event updates existing bids and offers to the expected energy
        rate"""
        future_strategy = FutureMarketStrategy(future_strategy_fixture.asset_type, 10, 50, 50, 20)
        self._setup_strategy_fixture(future_strategy_fixture)
        future_strategy_fixture.are_bids_posted = MagicMock(return_value=True)
        future_strategy_fixture.are_offers_posted = MagicMock(return_value=True)

        if isinstance(future_strategy_fixture, LoadHoursStrategy):
            future_strategy_fixture.state.set_desired_energy(2000.0, self.time_slot)
        if isinstance(future_strategy_fixture, PVStrategy):
            future_strategy_fixture.state.set_available_energy(300.0, self.time_slot)
        if isinstance(future_strategy_fixture, StorageStrategy):
            future_strategy_fixture.state.activate(duration(minutes=15), self.time_slot)
            future_strategy_fixture.get_available_energy_to_buy_kWh = Mock(return_value=3)
            future_strategy_fixture.get_available_energy_to_sell_kWh = Mock(return_value=2)
            future_strategy_fixture.state.offered_sell_kWh[self.time_slot] = 0.0
            future_strategy_fixture.state.offered_buy_kWh[self.time_slot] = 0.0
            future_strategy_fixture.state.pledged_sell_kWh[self.time_slot] = 0.0
            future_strategy_fixture.state.pledged_buy_kWh[self.time_slot] = 0.0
            future_strategy_fixture.state.register_energy_from_posted_offer = Mock()
            future_strategy_fixture.state.register_energy_from_posted_bid = Mock()
        future_strategy_fixture.area.current_tick = 0
        future_strategy.event_market_cycle(future_strategy_fixture)

        ticks_for_update = FutureTemplateStrategiesConstants.UPDATE_INTERVAL_MIN * 60 / 15
        future_strategy_fixture.area.current_tick = ticks_for_update - 1
        self.future_markets.bid.reset_mock()
        self.future_markets.offer.reset_mock()

        future_strategy_fixture.area.current_tick = ticks_for_update - 1
        future_strategy.event_tick(future_strategy_fixture)
        future_strategy_fixture.area.current_tick = ticks_for_update
        future_strategy.event_tick(future_strategy_fixture)
        number_of_updates = (
            ConstSettings.FutureMarketSettings.FUTURE_MARKET_DURATION_HOURS
            * 60
            / FutureTemplateStrategiesConstants.UPDATE_INTERVAL_MIN
        ) - 1
        bid_energy_rate = (50 - 10) / number_of_updates
        offer_energy_rate = (50 - 20) / number_of_updates
        if isinstance(future_strategy_fixture, LoadHoursStrategy):
            future_strategy_fixture.update_bid_rates.assert_called_once_with(
                self.future_markets, 10 + bid_energy_rate, self.time_slot
            )
        if isinstance(future_strategy_fixture, PVStrategy):
            future_strategy_fixture.update_offer_rates.assert_called_once_with(
                self.future_markets, 50 - offer_energy_rate, self.time_slot
            )
        if isinstance(future_strategy_fixture, StorageStrategy):
            future_strategy_fixture.update_bid_rates.assert_called_once_with(
                self.future_markets, 10 + bid_energy_rate, self.time_slot
            )
            future_strategy_fixture.update_offer_rates.assert_called_once_with(
                self.future_markets, 50 - offer_energy_rate, self.time_slot
            )

    @staticmethod
    def test_future_template_strategies_constants() -> None:
        """Validate that strategies constants are properly evaluated"""
        # pylint: disable=protected-access
        FutureTemplateStrategiesConstants.INITIAL_BUYING_RATE = 15
        FutureTemplateStrategiesConstants.FINAL_BUYING_RATE = 35
        FutureTemplateStrategiesConstants.INITIAL_SELLING_RATE = 30
        FutureTemplateStrategiesConstants.FINAL_SELLING_RATE = 10

        load_strategy_fixture = LoadHoursStrategy(100)
        assert load_strategy_fixture._future_market_strategy._bid_updater.initial_rate_input == 15
        assert load_strategy_fixture._future_market_strategy._bid_updater.final_rate_input == 35

        pv_strategy_fixture = PVStrategy()
        assert pv_strategy_fixture._future_market_strategy._offer_updater.initial_rate_input == 30
        assert pv_strategy_fixture._future_market_strategy._offer_updater.final_rate_input == 10
