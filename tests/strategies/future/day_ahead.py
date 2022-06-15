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

from gsy_framework.constants_limits import GlobalConfig, ConstSettings
from pendulum import duration, datetime

from gsy_e.models.market.day_ahead import DayAheadMarkets
from gsy_e.models.strategy.future.day_ahead import DayAheadMarketStrategy
from gsy_e.models.strategy.load_hours import LoadHoursStrategy
from gsy_e.models.strategy.pv import PVStrategy
from gsy_e.models.strategy.storage import StorageStrategy

if TYPE_CHECKING:
    from gsy_e.models.strategy import BaseStrategy

DEFAULT_CURRENT_MARKET_SLOT = datetime(2022, 6, 14, 0, 0)


class TestDayAheadMarketStrategy:
    # pylint: disable = attribute-defined-outside-init

    def setup_method(self) -> None:
        self._original_day_ahead_duration_days = (
            ConstSettings.FutureMarketSettings.DAY_AHEAD_DURATION_DAYS)
        GlobalConfig.DAY_AHEAD_DURATION_DAYS = 1
        self.time_slot = DEFAULT_CURRENT_MARKET_SLOT.add(days=1)
        self.area_mock = Mock()
        self.area_mock.name = "test_name"
        self.area_mock.uuid = str(uuid.uuid4())
        GlobalConfig.end_date = GlobalConfig.start_date + GlobalConfig.sim_duration
        self.area_mock.config = GlobalConfig
        self.day_ahead_markets = MagicMock(spec=DayAheadMarkets)
        self.day_ahead_markets.market_time_slots = [self.time_slot]
        self.day_ahead_markets.id = str(uuid.uuid4())

    def teardown_method(self) -> None:
        ConstSettings.FutureMarketSettings.DAY_AHEAD_DURATION_DAYS = (
            self._original_day_ahead_duration_days)

    def _setup_strategy_fixture(self, day_ahead_strategy_fixture: "BaseStrategy") -> None:
        day_ahead_strategy_fixture.owner = self.area_mock
        day_ahead_strategy_fixture.update_bid_rates = Mock()
        day_ahead_strategy_fixture.update_offer_rates = Mock()
        day_ahead_strategy_fixture.area = Mock()
        day_ahead_strategy_fixture.area.day_ahead_markets = self.day_ahead_markets
        day_ahead_strategy_fixture.area.current_tick = 0
        day_ahead_strategy_fixture.area.config = GlobalConfig
        day_ahead_strategy_fixture.area.config.tick_length = duration(seconds=15)

    def test_event_market_cycle_posts_bids_load(self) -> None:
        """Validate that market cycle event posts bids and offers for the load strategy"""
        load_strategy_fixture = LoadHoursStrategy(100)
        initial_selling_rate = 50
        final_selling_rate = 20
        day_ahead_strategy = DayAheadMarketStrategy(10, 50,
                                                    initial_selling_rate, final_selling_rate)
        self._setup_strategy_fixture(load_strategy_fixture)
        load_strategy_fixture.state.set_desired_energy(1234.0, self.time_slot)
        day_ahead_strategy.event_market_cycle(load_strategy_fixture)
        bid_rate = abs(initial_selling_rate-final_selling_rate)/2
        self.day_ahead_markets.bid.assert_called_once_with(
            bid_rate * 1.234, 1.234, self.area_mock.name, original_price=bid_rate * 1.234,
            buyer_origin=self.area_mock.name, buyer_origin_id=self.area_mock.uuid,
            buyer_id=self.area_mock.uuid, attributes=None, requirements=None,
            time_slot=self.time_slot
        )

    def test_event_market_cycle_posts_offers_pv(self) -> None:
        pv_strategy_fixture = PVStrategy()
        initial_buying_rate = 10
        final_buying_rate = 50
        day_ahead_strategy = DayAheadMarketStrategy(initial_buying_rate, final_buying_rate, 50, 20)
        self._setup_strategy_fixture(pv_strategy_fixture)
        pv_strategy_fixture.state.set_available_energy(321.3, self.time_slot)
        day_ahead_strategy.event_market_cycle(pv_strategy_fixture)
        offer_rate = abs(initial_buying_rate-final_buying_rate)/2
        self.day_ahead_markets.offer.assert_called_once_with(
            price=offer_rate * 321.3, energy=321.3, seller=self.area_mock.name,
            seller_origin=self.area_mock.name,
            seller_origin_id=self.area_mock.uuid, seller_id=self.area_mock.uuid,
            time_slot=self.time_slot
        )

    def test_event_market_cycle_posts_bids_and_offers_storage(self) -> None:
        storage_strategy_fixture = StorageStrategy()
        initial_selling_rate = 50
        final_selling_rate = 20
        initial_buying_rate = 10
        final_buying_rate = 50
        future_strategy = DayAheadMarketStrategy(initial_buying_rate, final_buying_rate,
                                                 initial_selling_rate, final_selling_rate)
        self._setup_strategy_fixture(storage_strategy_fixture)
        storage_strategy_fixture.state.activate(duration(minutes=15), self.time_slot)
        storage_strategy_fixture.state.offered_sell_kWh[self.time_slot] = 0.
        storage_strategy_fixture.state.offered_buy_kWh[self.time_slot] = 0.
        storage_strategy_fixture.state.pledged_sell_kWh[self.time_slot] = 0.
        storage_strategy_fixture.state.pledged_buy_kWh[self.time_slot] = 0.
        storage_strategy_fixture.state.get_available_energy_to_buy_kWh = Mock(return_value=3)
        storage_strategy_fixture.state.get_available_energy_to_sell_kWh = Mock(return_value=2)
        future_strategy.event_market_cycle(storage_strategy_fixture)
        offer_rate = abs(initial_buying_rate - final_buying_rate) / 2
        self.day_ahead_markets.offer.assert_called_once_with(
            price=offer_rate * 2, energy=2, seller=self.area_mock.name,
            seller_origin=self.area_mock.name,
            seller_origin_id=self.area_mock.uuid, seller_id=self.area_mock.uuid,
            time_slot=self.time_slot)
        bid_rate = abs(initial_selling_rate - final_selling_rate) / 2
        self.day_ahead_markets.bid.assert_called_once_with(
            bid_rate * 3, 3, self.area_mock.name, original_price=bid_rate * 3,
            buyer_origin=self.area_mock.name, buyer_origin_id=self.area_mock.uuid,
            buyer_id=self.area_mock.uuid, attributes=None, requirements=None,
            time_slot=self.time_slot
        )
