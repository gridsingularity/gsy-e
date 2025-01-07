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
from gsy_framework.constants_limits import ConstSettings, TIME_ZONE
from gsy_framework.data_classes import Bid, Offer, Trade, TraderDetails
from gsy_framework.utils import format_datetime
from pendulum import today, duration

from gsy_e.models.market.two_sided import TwoSidedMarket
from gsy_e.models.strategy.load_hours import LoadHoursStrategy
from gsy_e.models.strategy.pv import PVStrategy
from gsy_e.models.strategy.settlement.strategy import SettlementMarketStrategy


class TestSettlementMarketStrategy:
    # pylint: disable=attribute-defined-outside-init,too-many-instance-attributes
    def setup_method(self):
        ConstSettings.SettlementMarketSettings.ENABLE_SETTLEMENT_MARKETS = True
        self.settlement_strategy = SettlementMarketStrategy(10, 50, 50, 20)
        self.time_slot = today(tz=TIME_ZONE).at(hour=12, minute=0, second=0)
        self.market_mock = MagicMock(spec=TwoSidedMarket)
        self.market_mock.time_slot = self.time_slot
        self.market_mock.id = str(uuid.uuid4())
        self.test_bid = Bid("123", self.time_slot, 10, 1, buyer=TraderDetails("test_name", ""))
        self.test_offer = Offer(
            "234", self.time_slot, 50, 1, seller=TraderDetails("test_name", "")
        )
        self.market_mock.bid = MagicMock(return_value=self.test_bid)
        self.market_mock.offer = MagicMock(return_value=self.test_offer)
        self.market_mock.bids = {self.test_bid.id: self.test_bid}
        self.area_mock = Mock()
        self.area_mock.name = "test_name"
        self.area_mock.uuid = str(uuid.uuid4())
        self._area_trader_details = TraderDetails(self.area_mock.name, self.area_mock.uuid)
        self.settlement_markets = {self.time_slot: self.market_mock}

    def _setup_strategy_fixture(
        self, strategy_fixture, can_post_settlement_bid, can_post_settlement_offer
    ):
        strategy_fixture.owner = self.area_mock
        strategy_fixture.state.set_energy_measurement_kWh(1, self.time_slot)
        strategy_fixture.state.can_post_settlement_bid = MagicMock(
            return_value=can_post_settlement_bid
        )
        strategy_fixture.state.can_post_settlement_offer = MagicMock(
            return_value=can_post_settlement_offer
        )
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

    @staticmethod
    def teardown_method():
        ConstSettings.SettlementMarketSettings.ENABLE_SETTLEMENT_MARKETS = False

    @pytest.mark.parametrize("strategy_fixture", [LoadHoursStrategy(100), PVStrategy()])
    @pytest.mark.parametrize("can_post_settlement_bid", [True, False])
    @pytest.mark.parametrize("can_post_settlement_offer", [True, False])
    def test_event_market_cycle_posts_bids_and_offers(
        self, strategy_fixture, can_post_settlement_bid, can_post_settlement_offer
    ):
        self._setup_strategy_fixture(
            strategy_fixture, can_post_settlement_bid, can_post_settlement_offer
        )
        self.settlement_strategy.event_market_cycle(strategy_fixture)
        if can_post_settlement_bid:
            self.market_mock.bid.assert_called_once_with(
                10.0,
                1.0,
                TraderDetails(
                    self.area_mock.name,
                    self.area_mock.uuid,
                    self.area_mock.name,
                    self.area_mock.uuid,
                ),
                original_price=10.0,
                time_slot=self.time_slot,
            )
        if can_post_settlement_offer:
            self.market_mock.offer.assert_called_once_with(
                price=50.0,
                energy=1.0,
                seller=TraderDetails(
                    self.area_mock.name,
                    self.area_mock.uuid,
                    self.area_mock.name,
                    self.area_mock.uuid,
                ),
                time_slot=self.time_slot,
            )

    @pytest.mark.parametrize("strategy_fixture", [LoadHoursStrategy(100), PVStrategy()])
    @pytest.mark.parametrize("can_post_settlement_bid", [True, False])
    @pytest.mark.parametrize("can_post_settlement_offer", [True, False])
    def test_event_tick_updates_bids_and_offers(
        self, strategy_fixture, can_post_settlement_bid, can_post_settlement_offer
    ):
        self._setup_strategy_fixture(
            strategy_fixture, can_post_settlement_bid, can_post_settlement_offer
        )

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
                30.0,
                1.0,
                TraderDetails(
                    self.area_mock.name,
                    self.area_mock.uuid,
                    self.area_mock.name,
                    self.area_mock.uuid,
                ),
                original_price=30.0,
                time_slot=self.time_slot,
            )
        if can_post_settlement_offer:
            self.market_mock.offer.assert_called_once_with(
                35.0,
                1,
                TraderDetails(self.area_mock.name, self.area_mock.uuid),
                original_price=35.0,
                time_slot=self.time_slot,
            )

    @pytest.mark.parametrize("strategy_fixture", [LoadHoursStrategy(100), PVStrategy()])
    def test_event_trade_updates_energy_deviation(self, strategy_fixture):
        self._setup_strategy_fixture(strategy_fixture, False, True)
        strategy_fixture.state.set_energy_measurement_kWh(10, self.time_slot)
        self.settlement_strategy.event_market_cycle(strategy_fixture)
        self.settlement_strategy.event_offer_traded(
            strategy_fixture,
            self.market_mock.id,
            Trade(
                "456",
                self.time_slot,
                self._area_trader_details,
                self._area_trader_details,
                offer=self.test_offer,
                traded_energy=1,
                trade_price=1,
            ),
        )
        assert strategy_fixture.state.get_unsettled_deviation_kWh(self.time_slot) == 9

    @pytest.mark.parametrize("strategy_fixture", [LoadHoursStrategy(100), PVStrategy()])
    def test_event_trade_not_update_energy_deviation_on_bid_trade(self, strategy_fixture):
        self._setup_strategy_fixture(strategy_fixture, False, True)
        strategy_fixture.state.set_energy_measurement_kWh(10, self.time_slot)
        self.settlement_strategy.event_market_cycle(strategy_fixture)
        self.settlement_strategy.event_offer_traded(
            strategy_fixture,
            self.market_mock.id,
            Trade(
                "456",
                self.time_slot,
                self._area_trader_details,
                self._area_trader_details,
                bid=self.test_bid,
                traded_energy=1,
                trade_price=1,
            ),
        )
        assert strategy_fixture.state.get_unsettled_deviation_kWh(self.time_slot) == 10

    @pytest.mark.parametrize("strategy_fixture", [LoadHoursStrategy(100), PVStrategy()])
    def test_event_bid_trade_updates_energy_deviation(self, strategy_fixture):
        self._setup_strategy_fixture(strategy_fixture, True, False)
        strategy_fixture.state.set_energy_measurement_kWh(15, self.time_slot)
        self.settlement_strategy.event_market_cycle(strategy_fixture)
        self.settlement_strategy.event_bid_traded(
            strategy_fixture,
            self.market_mock.id,
            Trade(
                "456",
                self.time_slot,
                self._area_trader_details,
                self._area_trader_details,
                bid=self.test_bid,
                traded_energy=1,
                trade_price=1,
            ),
        )
        assert strategy_fixture.state.get_unsettled_deviation_kWh(self.time_slot) == 14

    @pytest.mark.parametrize("strategy_fixture", [LoadHoursStrategy(100), PVStrategy()])
    def test_event_bid_traded_does_not_update_energy_deviation_offer_trade(self, strategy_fixture):
        self._setup_strategy_fixture(strategy_fixture, True, False)
        strategy_fixture.state.set_energy_measurement_kWh(15, self.time_slot)
        self.settlement_strategy.event_market_cycle(strategy_fixture)
        self.settlement_strategy.event_bid_traded(
            strategy_fixture,
            self.market_mock.id,
            Trade(
                "456",
                self.time_slot,
                self._area_trader_details,
                self._area_trader_details,
                offer=self.test_offer,
                traded_energy=1,
                trade_price=1,
            ),
        )
        assert strategy_fixture.state.get_unsettled_deviation_kWh(self.time_slot) == 15

    @pytest.mark.parametrize("strategy_fixture", [LoadHoursStrategy(100), PVStrategy()])
    def test_get_unsettled_deviation_dict(self, strategy_fixture):
        self._setup_strategy_fixture(strategy_fixture, True, False)
        strategy_fixture.state.set_energy_measurement_kWh(15, self.time_slot)
        unsettled_deviation_dict = self.settlement_strategy.get_unsettled_deviation_dict(
            strategy_fixture
        )
        assert len(unsettled_deviation_dict["unsettled_deviation_kWh"]) == 1
        assert list(unsettled_deviation_dict["unsettled_deviation_kWh"].keys()) == [
            format_datetime(self.time_slot)
        ]
        assert list(unsettled_deviation_dict["unsettled_deviation_kWh"].values()) == [
            strategy_fixture.state.get_signed_unsettled_deviation_kWh(self.time_slot)
        ]

    @pytest.mark.parametrize("strategy_fixture", [LoadHoursStrategy(100), PVStrategy()])
    def test_get_market_from_id_works_for_settlement_markets(self, strategy_fixture):
        self._setup_strategy_fixture(strategy_fixture, True, True)
        market = strategy_fixture.get_market_from_id(self.settlement_markets[self.time_slot].id)
        assert market == self.settlement_markets[self.time_slot]

    def test_can_get_settlement_bid_be_posted(self):
        strategy_fixture = LoadHoursStrategy(100)
        self._setup_strategy_fixture(strategy_fixture, True, False)

        assert (
            strategy_fixture.can_settlement_offer_be_posted(
                1.1, 1, self.settlement_markets[self.time_slot]
            )
            is False
        )

        assert (
            strategy_fixture.can_settlement_bid_be_posted(
                0.9, 1, self.settlement_markets[self.time_slot]
            )
            is True
        )

        assert (
            strategy_fixture.can_settlement_bid_be_posted(
                1.1, 1, self.settlement_markets[self.time_slot]
            )
            is False
        )

    def test_can_get_settlement_offer_be_posted(self):
        strategy_fixture = PVStrategy()
        self._setup_strategy_fixture(strategy_fixture, False, True)

        assert (
            strategy_fixture.can_settlement_bid_be_posted(
                1.1, 1, self.settlement_markets[self.time_slot]
            )
            is False
        )

        assert (
            strategy_fixture.can_settlement_offer_be_posted(
                0.9, 1, self.settlement_markets[self.time_slot]
            )
            is True
        )

        assert (
            strategy_fixture.can_settlement_offer_be_posted(
                1.1, 1, self.settlement_markets[self.time_slot]
            )
            is False
        )
