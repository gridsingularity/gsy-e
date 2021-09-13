import uuid
from unittest.mock import Mock, MagicMock

import pytest
from d3a_interface.constants_limits import ConstSettings
from pendulum import today, duration

from d3a.constants import TIME_ZONE
from d3a.models.market.market_structures import Bid, Offer, Trade
from d3a.models.market.two_sided import TwoSidedMarket
from d3a.models.strategy.load_hours import LoadHoursStrategy
from d3a.models.strategy.pv import PVStrategy
from d3a.models.strategy.settlement.strategy import SettlementMarketStrategy


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
                10.0, 1.0, self.area_mock.name, original_bid_price=10.0,
                buyer_origin=self.area_mock.name, buyer_origin_id=self.area_mock.uuid,
                buyer_id=self.area_mock.uuid, attributes=None, requirements=None
            )
        if can_post_settlement_offer:
            self.market_mock.offer.assert_called_once_with(
                price=50.0, energy=1.0, seller=self.area_mock.name,
                seller_origin=self.area_mock.name,
                seller_origin_id=self.area_mock.uuid, seller_id=self.area_mock.uuid
            )

    @pytest.mark.parametrize(
        "strategy_fixture", [LoadHoursStrategy(100), PVStrategy()])
    @pytest.mark.parametrize("can_post_settlement_bid", [True, False])
    @pytest.mark.parametrize("can_post_settlement_offer", [True, False])
    def test_event_tick_updates_bids_and_offers(
            self, strategy_fixture, can_post_settlement_bid, can_post_settlement_offer):
        self._setup_strategy_fixture(
            strategy_fixture, can_post_settlement_bid, can_post_settlement_offer)
        self.settlement_strategy.event_market_cycle(strategy_fixture)

        strategy_fixture.area.current_tick = 30
        strategy_fixture.area.config = Mock()
        strategy_fixture.area.config.ticks_per_slot = 60
        strategy_fixture.area.config.tick_length = duration(seconds=15)
        self.market_mock.bid.reset_mock()
        self.market_mock.offer.reset_mock()

        self.settlement_strategy.event_tick(strategy_fixture)
        if can_post_settlement_bid:
            self.market_mock.bid.assert_called_once_with(
                30.0, 1.0, self.area_mock.name, original_bid_price=30.0,
                buyer_origin=self.area_mock.name, buyer_origin_id=self.area_mock.uuid,
                buyer_id=self.area_mock.uuid, attributes=None, requirements=None
            )
        if can_post_settlement_offer:
            self.market_mock.offer.assert_called_once_with(
                35, 1, self.area_mock.name, original_offer_price=35,
                seller_origin=None, seller_origin_id=None, seller_id=self.area_mock.uuid
            )

    @pytest.mark.parametrize(
        "strategy_fixture", [LoadHoursStrategy(100), PVStrategy()])
    def test_event_trade_updates_energy_deviation(self, strategy_fixture):
        self._setup_strategy_fixture(strategy_fixture, False, True)
        strategy_fixture.state.set_energy_measurement_kWh(10, self.time_slot)
        self.settlement_strategy.event_market_cycle(strategy_fixture)
        self.settlement_strategy.event_trade(
            strategy_fixture, self.market_mock.id,
            Trade("456", self.time_slot, self.test_offer, self.area_mock.name, self.area_mock.name)
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
            Trade("456", self.time_slot, self.test_bid, self.area_mock.name, self.area_mock.name)
        )
        assert strategy_fixture.state.get_unsettled_deviation_kWh(self.time_slot) == 14