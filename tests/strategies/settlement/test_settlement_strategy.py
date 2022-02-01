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
import uuid
from unittest.mock import Mock, MagicMock

import pytest
from gsy_framework.constants_limits import ConstSettings
from gsy_framework.data_classes import Bid, Offer, Trade
from pendulum import today, duration

from gsy_e.constants import TIME_ZONE
from gsy_e.models.market.two_sided import TwoSidedMarket
from gsy_e.models.strategy.load_hours import LoadHoursStrategy
from gsy_e.models.strategy.pv import PVStrategy
from gsy_e.models.strategy.settlement.strategy import SettlementMarketStrategy


class TestSettlementMarketStrategy:

    def setup_method(self):
        ConstSettings.SettlementMarketSettings.ENABLE_SETTLEMENT_MARKETS = True
        self.settlement_strategy = SettlementMarketStrategy(10, 50, 50, 20)
        self.time_slot = today(tz=TIME_ZONE).at(hour=12, minute=0, second=0)
        self.market_mock = MagicMock(spec=TwoSidedMarket)
        self.market_mock.time_slot = self.time_slot
        self.market_mock.id = str(uuid.uuid4())
        self.test_bid = Bid("123", self.time_slot, 10, 1, buyer="test_name")
        self.test_offer = Offer("234", self.time_slot, 50, 1, seller="test_name")
        self.market_mock.bid = MagicMock(return_value=self.test_bid)
        self.market_mock.offer = MagicMock(return_value=self.test_offer)
        self.market_mock.bids = {self.test_bid.id: self.test_bid}
        self.area_mock = Mock()
        self.area_mock.name = "test_name"
        self.area_mock.uuid = str(uuid.uuid4())
        self.settlement_markets = {
            self.time_slot: self.market_mock
        }

    def _setup_strategy_fixture(
            self, strategy_fixture, can_post_settlement_bid, can_post_settlement_offer):
        strategy_fixture.owner = self.area_mock
        strategy_fixture.state.set_energy_measurement_kWh(1, self.time_slot)
        strategy_fixture.state.can_post_settlement_bid = MagicMock(
            return_value=can_post_settlement_bid)
        strategy_fixture.state.can_post_settlement_offer = MagicMock(
            return_value=can_post_settlement_offer)
        strategy_fixture.area = Mock()
        strategy_fixture.area.settlement_markets = self.settlement_markets
        strategy_fixture.get_market_from_id = MagicMock(return_value=self.market_mock)
        strategy_fixture.area.current_tick = 0
        strategy_fixture.area.config = Mock()
        strategy_fixture.simulation_config.ticks_per_slot = 60
        strategy_fixture.simulation_config.tick_length = duration(seconds=15)
        strategy_fixture.simulation_config.start_date = today()
        strategy_fixture.simulation_config.sim_duration = duration(days=1)
        strategy_fixture.simulation_config.end_date = today() + duration(days=1)

    def teardown_method(self):
        ConstSettings.SettlementMarketSettings.ENABLE_SETTLEMENT_MARKETS = False

    @pytest.mark.parametrize(
        "strategy_fixture", [LoadHoursStrategy(100), PVStrategy()])
    @pytest.mark.parametrize("can_post_settlement_bid", [True, False])
    @pytest.mark.parametrize("can_post_settlement_offer", [True, False])
    def test_event_market_cycle_posts_bids_and_offers(
            self, strategy_fixture, can_post_settlement_bid, can_post_settlement_offer):
        self._setup_strategy_fixture(
            strategy_fixture, can_post_settlement_bid, can_post_settlement_offer)
        self.settlement_strategy.event_market_cycle(strategy_fixture)
        if can_post_settlement_bid:
            self.market_mock.bid.assert_called_once_with(
                10.0, 1.0, self.area_mock.name, original_price=10.0,
                buyer_origin=self.area_mock.name, buyer_origin_id=self.area_mock.uuid,
                buyer_id=self.area_mock.uuid, attributes=None, requirements=None,
                time_slot=self.time_slot
            )
        if can_post_settlement_offer:
            self.market_mock.offer.assert_called_once_with(
                price=50.0, energy=1.0, seller=self.area_mock.name,
                seller_origin=self.area_mock.name,
                seller_origin_id=self.area_mock.uuid, seller_id=self.area_mock.uuid,
                time_slot=self.time_slot
            )

    @pytest.mark.parametrize(
        "strategy_fixture", [LoadHoursStrategy(100), PVStrategy()])
    @pytest.mark.parametrize("can_post_settlement_bid", [True, False])
    @pytest.mark.parametrize("can_post_settlement_offer", [True, False])
    def test_event_tick_updates_bids_and_offers(
            self, strategy_fixture, can_post_settlement_bid, can_post_settlement_offer):
        self._setup_strategy_fixture(
            strategy_fixture, can_post_settlement_bid, can_post_settlement_offer)

        strategy_fixture.area.current_tick = 0
        self.settlement_strategy.event_market_cycle(strategy_fixture)

        strategy_fixture.area.current_tick = 30
        self.market_mock.bid.reset_mock()
        self.market_mock.offer.reset_mock()

        strategy_fixture.area.current_tick = 19
        self.settlement_strategy.event_tick(strategy_fixture)
        strategy_fixture.area.current_tick = 20
        self.settlement_strategy.event_tick(strategy_fixture)
        if can_post_settlement_bid:
            self.market_mock.bid.assert_called_once_with(
                30.0, 1.0, self.area_mock.name, original_price=30.0,
                buyer_origin=self.area_mock.name, buyer_origin_id=self.area_mock.uuid,
                buyer_id=self.area_mock.uuid, attributes=None, requirements=None,
                time_slot=self.time_slot
            )
        if can_post_settlement_offer:
            self.market_mock.offer.assert_called_once_with(
                35, 1, self.area_mock.name, original_price=35,
                seller_origin=None, seller_origin_id=None, seller_id=self.area_mock.uuid,
                time_slot=self.time_slot
            )

    @pytest.mark.parametrize(
        "strategy_fixture", [LoadHoursStrategy(100), PVStrategy()])
    def test_event_trade_updates_energy_deviation(self, strategy_fixture):
        self._setup_strategy_fixture(strategy_fixture, False, True)
        strategy_fixture.state.set_energy_measurement_kWh(10, self.time_slot)
        self.settlement_strategy.event_market_cycle(strategy_fixture)
        self.settlement_strategy.event_offer_traded(
            strategy_fixture, self.market_mock.id,
            Trade("456", self.time_slot, self.test_offer, self.area_mock.name, self.area_mock.name,
                  traded_energy=1, trade_price=1)
        )
        assert strategy_fixture.state.get_unsettled_deviation_kWh(self.time_slot) == 9

    @pytest.mark.parametrize(
        "strategy_fixture", [LoadHoursStrategy(100), PVStrategy()])
    def test_event_bid_trade_updates_energy_deviation(self, strategy_fixture):
        self._setup_strategy_fixture(strategy_fixture, True, False)
        strategy_fixture.state.set_energy_measurement_kWh(15, self.time_slot)
        self.settlement_strategy.event_market_cycle(strategy_fixture)
        self.settlement_strategy.event_bid_traded(
            strategy_fixture, self.market_mock.id,
            Trade("456", self.time_slot, self.test_bid, self.area_mock.name, self.area_mock.name,
                  traded_energy=1, trade_price=1)
        )
        assert strategy_fixture.state.get_unsettled_deviation_kWh(self.time_slot) == 14

    @pytest.mark.parametrize(
        "strategy_fixture", [LoadHoursStrategy(100), PVStrategy()])
    def test_get_unsettled_deviation_dict(self, strategy_fixture):
        self._setup_strategy_fixture(strategy_fixture, True, False)
        strategy_fixture.state.set_energy_measurement_kWh(15, self.time_slot)
        unsettled_deviation_dict = self.settlement_strategy.get_unsettled_deviation_dict(
            strategy_fixture)
        from gsy_framework.utils import format_datetime
        assert len(unsettled_deviation_dict["unsettled_deviation_kWh"]) == 1
        assert (list(unsettled_deviation_dict["unsettled_deviation_kWh"].keys()) ==
                [format_datetime(self.time_slot)])
        assert (list(unsettled_deviation_dict["unsettled_deviation_kWh"].values()) ==
                [strategy_fixture.state.get_signed_unsettled_deviation_kWh(self.time_slot)])
