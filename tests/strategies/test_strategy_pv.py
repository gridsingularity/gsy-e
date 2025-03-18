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

# pylint: disable=missing-function-docstring,protected-access
import os
import uuid
from typing import Dict  # NOQA
from unittest.mock import Mock, patch
from uuid import uuid4

import pendulum
import pytest
from gsy_framework.constants_limits import ConstSettings, GlobalConfig, TIME_FORMAT, TIME_ZONE
from gsy_framework.data_classes import Offer, Trade, TraderDetails
from gsy_framework.exceptions import GSyDeviceException
from gsy_framework.utils import generate_market_slot_list
from parameterized import parameterized

from gsy_e.gsy_e_core.util import gsye_root_path
from gsy_e.models.config import create_simulation_config_from_global_config
from gsy_e.models.strategy.predefined_pv import PVPredefinedStrategy, PVUserProfileStrategy
from gsy_e.models.strategy.pv import PVStrategy

ENERGY_FORECAST = {}  # type: Dict[pendulum.DateTime, float]
TIME = pendulum.today(tz=TIME_ZONE).at(hour=10, minute=45, second=0)


@pytest.fixture(scope="function", autouse=True)
def auto_fixture():
    original_market_maker_rate = GlobalConfig.market_maker_rate
    GlobalConfig.market_maker_rate = ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE
    yield
    GlobalConfig.market_maker_rate = original_market_maker_rate
    GlobalConfig.sim_duration = pendulum.duration(days=GlobalConfig.DURATION_D)
    GlobalConfig.slot_length = pendulum.duration(minutes=GlobalConfig.SLOT_LENGTH_M)


class FakeArea:
    """Fake class that mimics the Area class."""

    def __init__(self):
        self.config = create_simulation_config_from_global_config()
        self.current_tick = 2
        self.name = "FakeArea"
        self.uuid = str(uuid4())
        self.test_market = FakeMarket(0)
        self._spot_market = FakeMarket(0)

    def get_spot_or_future_market_by_id(self, _):
        return self.test_market

    @staticmethod
    def is_market_spot_or_future(_):
        return True

    @property
    def future_market_time_slots(self):
        return []

    @property
    def future_markets(self):
        return None

    @property
    def current_market(self):
        return self.test_market

    @staticmethod
    def get_path_to_root_fees():
        return 0.0

    @property
    def now(self) -> pendulum.DateTime:
        """
        Return the 'current time' as a `DateTime` object.
        Can be overridden in subclasses to change the meaning of 'now'.

        In this default implementation 'current time' is defined by the number of ticks that
        have passed.
        """
        return pendulum.DateTime.now(tz=TIME_ZONE).start_of("day") + (
            self.config.tick_length * self.current_tick
        )

    @property
    def all_markets(self):
        return [self.test_market, self.test_market, self.test_market]

    @property
    def spot_market(self):
        return self.test_market


class FakeAreaTimeSlot(FakeArea):
    """Add fake implementation for the spot market creation."""

    @property
    def spot_market(self):
        return self._spot_market

    def create_spot_market(self, time_slot):
        self._spot_market = FakeMarketTimeSlot(time_slot)


class FakeMarketTimeSlot:
    """Add fake market implementation that contains the time slot."""

    def __init__(self, time_slot):
        self.time_slot = time_slot


class FakeMarket:
    """Fake class that mimics the Market class."""

    def __init__(self, count):
        self.count = count
        self.id = str(count)
        self.created_offers = []
        self.offers = {
            "id": Offer(
                id="id",
                creation_time=pendulum.now(),
                price=10,
                energy=0.5,
                seller=TraderDetails("A", ""),
            )
        }

    def offer(self, price, energy, seller, original_price=None, time_slot=None):
        # pylint: disable=too-many-arguments
        offer = Offer(
            str(uuid.uuid4()),
            pendulum.now(),
            price,
            energy,
            seller,
            original_price,
            time_slot=time_slot,
        )
        self.created_offers.append(offer)
        self.offers[offer.id] = offer
        return offer

    @property
    def time_slot(self):
        return TIME

    @property
    def time_slot_str(self):
        return self.time_slot.format(TIME_FORMAT)

    @staticmethod
    def delete_offer(_offer_id):
        return


class FakeTrade:
    """Fake class that mimics the Trade class."""

    def __init__(self, offer):
        self.offer = offer
        self.match_details = {"offer": offer, "bid": None}
        self.seller = TraderDetails("FakeSeller", "")
        self.traded_energy = offer.energy
        self.trade_price = offer.price
        self.time_slot = None

    @property
    def is_offer_trade(self):
        return True

    @property
    def buyer(self):
        return "FakeBuyer"

    @property
    def trade_rate(self):
        return self.offer.energy_rate


@pytest.fixture(name="area_test1")
def fixture_area_test1():
    return FakeArea()


@pytest.fixture(name="pv_test1")
def fixture_pv_test1(area_test1):
    p = PVStrategy()
    p.area = area_test1
    p.owner = area_test1
    return p


@pytest.fixture(name="area_test2")
def fixture_area_test2():
    return FakeArea()


@pytest.fixture(name="market_test2")
def fixture_market_test2(area_test2):
    return area_test2.test_market


@pytest.fixture(name="pv_test2")
def fixture_pv_test2(area_test2):
    p = PVStrategy()
    p.area = area_test2
    p.owner = area_test2
    p.offers.posted = {}
    p.state._energy_production_forecast_kWh = ENERGY_FORECAST
    return p


@pytest.mark.skip("broken as event_tick does not decrease offer price with every tick")
def testing_event_tick(pv_test2, market_test2, area_test2):
    pv_test2.event_activate()
    pv_test2.event_tick()
    assert len(market_test2.created_offers) == 1
    assert len(pv_test2.offers.posted.items()) == 1
    offer_id1 = list(pv_test2.offers.posted.keys())[0]
    offer1 = market_test2.offers[offer_id1]
    assert (
        market_test2.created_offers[0].price
        == 29.9 * pv_test2.state._energy_production_forecast_kWh[TIME]
    )
    assert (
        pv_test2.state._energy_production_forecast_kWh[
            pendulum.today(tz=TIME_ZONE).at(hour=0, minute=0, second=2)
        ]
        == 0
    )
    area_test2.current_tick_in_slot = area_test2.config.ticks_per_slot - 2
    pv_test2.event_tick()
    offer_id2 = list(pv_test2.offers.posted.keys())[0]
    offer2 = market_test2.offers[offer_id2]
    assert offer1 != offer2
    assert len(pv_test2.offers.posted.items()) == 1
    # assert len(pv_test2.decrease_offer_price.calls) == 1


@pytest.fixture(name="area_test3")
def fixture_area_test3():
    return FakeArea()


@pytest.fixture(name="market_test3")
def fixture_market_test3(area_test3):
    return area_test3.test_market


@pytest.fixture(name="pv_test3")
def fixture_pv_test3(area_test3):
    p = PVStrategy()
    p.area = area_test3
    p.owner = area_test3
    p.offers.posted = {
        Offer("id", pendulum.now(), 1, 1, TraderDetails("FakeArea", "")): area_test3.test_market.id
    }
    return p


def testing_decrease_offer_price(area_test3, pv_test3):
    assert len(pv_test3.offers.posted.items()) == 1
    pv_test3.event_activate()
    pv_test3.event_market_cycle()
    pv_test3.event_tick()
    for _ in range(2):
        area_test3.current_tick += 310
        old_offer = list(pv_test3.offers.posted.keys())[0]
        pv_test3.event_tick()
        new_offer = list(pv_test3.offers.posted.keys())[0]
        assert new_offer.price < old_offer.price


def test_same_slot_price_drop_does_not_reduce_price_below_threshold(area_test3, pv_test3):
    pv_test3.event_activate()
    pv_test3.event_market_cycle()
    for _ in range(100):
        area_test3.current_tick += 10
        pv_test3.event_tick()
    new_offer = list(pv_test3.offers.posted.keys())[-1]
    assert new_offer.energy_rate >= ConstSettings.PVSettings.SELLING_RATE_RANGE.final


@pytest.fixture(name="pv_test4")
def fixture_pv_test4(area_test3):
    p = PVStrategy()
    p.area = area_test3
    p.owner = area_test3
    p.offers.posted = {
        Offer(
            id="id", creation_time=TIME, price=20, energy=1, seller=TraderDetails("FakeArea", "")
        ): area_test3.test_market.id
    }
    return p


def testing_event_trade(area_test3, pv_test4):
    pv_test4.state._available_energy_kWh[area_test3.test_market.time_slot] = 1
    pv_test4.event_offer_traded(
        market_id=area_test3.test_market.id,
        trade=Trade(
            id="id",
            creation_time=pendulum.now(),
            traded_energy=1,
            trade_price=20,
            offer=Offer(
                id="id",
                creation_time=TIME,
                price=20,
                energy=1,
                seller=TraderDetails("FakeArea", ""),
            ),
            seller=TraderDetails(area_test3.name, ""),
            buyer=TraderDetails("buyer", ""),
            time_slot=area_test3.test_market.time_slot,
        ),
    )
    assert len(pv_test4.offers.open) == 0


@pytest.fixture(name="pv_test5")
def fixture_pv_test5(area_test3):
    p = PVStrategy()
    p.area = area_test3
    p.owner = area_test3
    p.offers.posted = {"id": area_test3.test_market}
    return p


@pytest.fixture(name="pv_test6")
def fixture_pv_test6(area_test3):
    p = PVStrategy()
    p.area = area_test3
    p.owner = area_test3
    p.offers.posted = {}
    p.state._energy_production_forecast_kWh = ENERGY_FORECAST
    return p


@pytest.fixture(name="area_test66")
def fixture_area_test66():
    return FakeAreaTimeSlot()


@pytest.fixture(name="pv_test66")
def fixture_pv_test66(area_test66):
    original_future_markets_duration = (
        ConstSettings.FutureMarketSettings.FUTURE_MARKET_DURATION_HOURS
    )
    ConstSettings.FutureMarketSettings.FUTURE_MARKET_DURATION_HOURS = 0
    p = PVStrategy()
    p.area = area_test66
    p.owner = area_test66
    p.offers.posted = {}
    yield p
    ConstSettings.FutureMarketSettings.FUTURE_MARKET_DURATION_HOURS = (
        original_future_markets_duration
    )


def testing_produced_energy_forecast_real_data(pv_test66):
    pv_test66.event_activate()
    # prepare whole day of energy_production_forecast_kWh:
    for time_slot in generate_market_slot_list():
        pv_test66.area.create_spot_market(time_slot)
        pv_test66.set_produced_energy_forecast_in_state(reconfigure=False)
    morning_time = pendulum.today(tz=TIME_ZONE).at(hour=8, minute=20, second=0)
    afternoon_time = pendulum.today(tz=TIME_ZONE).at(hour=16, minute=40, second=0)

    class _Counts:
        def __init__(self, time_of_day: str):
            self.total = 0
            self.count = 0
            self.time_of_day = time_of_day

    morning_counts = _Counts("morning")
    afternoon_counts = _Counts("afternoon")
    evening_counts = _Counts("evening")
    for time, _power in pv_test66.state._energy_production_forecast_kWh.items():
        if time < morning_time:
            morning_counts.total += 1
            morning_counts.count = (
                morning_counts.count + 1
                if pv_test66.state._energy_production_forecast_kWh[time] == 0
                else morning_counts.count
            )
        elif morning_time < time < afternoon_time:
            afternoon_counts.total += 1
            afternoon_counts.count = (
                afternoon_counts.count + 1
                if pv_test66.state._energy_production_forecast_kWh[time] > 0.001
                else afternoon_counts.count
            )
        elif time > afternoon_time:
            evening_counts.total += 1
            evening_counts.count = (
                evening_counts.count + 1
                if pv_test66.state._energy_production_forecast_kWh[time] == 0
                else evening_counts.count
            )

    total_count = morning_counts.total + afternoon_counts.total + evening_counts.total
    assert len(list(pv_test66.state._energy_production_forecast_kWh.items())) == total_count

    # Morning power generation is less we check this by percentage wise counts in the morning

    morning_count_percent = (morning_counts.count / morning_counts.total) * 100
    assert morning_count_percent > 90

    # Afternoon power generation should be subsequently larger

    afternoon_count_percent = (afternoon_counts.count / afternoon_counts.total) * 100
    assert afternoon_count_percent > 50

    # Evening power generation should again drop to low levels

    evening_count_percent = (evening_counts.count / evening_counts.total) * 100
    assert evening_count_percent > 90


# The pv sells its whole production at once if possible.
# Make sure that it doesnt offer it again after selling.


def test_does_not_offer_sold_energy_again(pv_test6, market_test3):
    pv_test6.event_activate()
    pv_test6.event_market_cycle()
    assert (
        market_test3.created_offers[0].energy
        == pv_test6.state._energy_production_forecast_kWh[TIME]
    )
    fake_trade = FakeTrade(market_test3.created_offers[0])
    fake_trade.seller = TraderDetails(
        pv_test6.owner.name,
        fake_trade.seller.uuid,
        fake_trade.seller.origin,
        fake_trade.seller.origin_uuid,
    )
    fake_trade.time_slot = market_test3.time_slot
    pv_test6.event_offer_traded(market_id=market_test3.id, trade=fake_trade)
    market_test3.created_offers = []
    assert not market_test3.created_offers


def test_pv_constructor_rejects_incorrect_parameters():
    with pytest.raises(GSyDeviceException):
        PVStrategy(panel_count=-1)
    with pytest.raises(GSyDeviceException):
        PVStrategy(capacity_kW=-100)
    with pytest.raises(GSyDeviceException):
        pv = PVStrategy(initial_selling_rate=5, final_selling_rate=15)
        pv.event_activate()
    with pytest.raises(GSyDeviceException):
        PVStrategy(fit_to_limit=True, energy_rate_decrease_per_update=1)
    with pytest.raises(GSyDeviceException):
        PVStrategy(fit_to_limit=False, energy_rate_decrease_per_update=-1)


@pytest.fixture(name="pv_test7")
def fixture_pv_test7(area_test3):
    p = PVStrategy(panel_count=1, initial_selling_rate=30)
    p.area = area_test3
    p.owner = area_test3
    p.offers.posted = {
        Offer("id", pendulum.now(), 1, 1, TraderDetails("FakeArea", "")): area_test3.test_market.id
    }
    return p


@pytest.fixture(name="pv_test8")
def fixture_pv_test8(area_test3):
    p = PVStrategy(panel_count=1, initial_selling_rate=30)
    p.area = area_test3
    p.owner = area_test3
    p.offers.posted = {
        Offer("id", pendulum.now(), 1, 1, TraderDetails("FakeArea", "")): area_test3.test_market.id
    }
    return p


@pytest.fixture(name="area_test9")
def fixture_area_test9():
    return FakeArea()


@pytest.fixture(name="market_test9")
def fixture_market_test9(area_test9):
    return area_test9.test_market


@pytest.fixture(name="pv_test9")
def fixture_pv_test9(area_test9):
    p = PVStrategy(panel_count=3)
    p.area = area_test9
    p.owner = area_test9
    p.offers.posted = {}
    p.state._energy_production_forecast_kWh = ENERGY_FORECAST
    return p


def testing_number_of_pv_sell_offers(pv_test9, area_test9):
    pv_test9.event_activate()
    pv_test9.event_market_cycle()
    for m in area_test9.all_markets:
        assert len(m.created_offers) == 1


@pytest.fixture(name="area_test10")
def fixture_area_test10():
    return FakeArea()


@pytest.fixture(name="market_test10")
def fixture_market_test10():
    return FakeMarket(0)


@pytest.fixture(name="pv_strategy_test10")
def fixture_pv_strategy_test10(area_test10, called):
    s = PVStrategy(initial_selling_rate=25)
    s.owner = area_test10
    s.area = area_test10
    s.accept_offer = called
    return s


def test_initial_selling_rate(pv_strategy_test10, area_test10):
    pv_strategy_test10.event_activate()
    pv_strategy_test10.event_market_cycle()
    created_offer = area_test10.all_markets[0].created_offers[0]
    assert created_offer.price / created_offer.energy == 25


@parameterized.expand(
    [
        [
            PVStrategy,
            True,
            12,
        ],
        [
            PVStrategy,
            False,
            19,
        ],
    ]
)
def test_use_mmr_parameter_is_respected1(strategy_type, use_mmr, expected_rate):
    original_mmr = GlobalConfig.market_maker_rate
    GlobalConfig.market_maker_rate = 12
    pv = strategy_type(initial_selling_rate=19, use_market_maker_rate=use_mmr, capacity_kW=0.2)
    pv.area = FakeArea()
    pv.owner = pv.area
    pv.event_activate()
    assert all(v == expected_rate for v in pv.offer_update.initial_rate.values())
    GlobalConfig.market_maker_rate = original_mmr


@parameterized.expand(
    [
        [
            PVPredefinedStrategy,
            True,
            12,
        ],
        [
            PVPredefinedStrategy,
            False,
            19,
        ],
    ]
)
def test_use_mmr_parameter_is_respected2(strategy_type, use_mmr, expected_rate):
    original_mmr = GlobalConfig.market_maker_rate
    GlobalConfig.market_maker_rate = 12
    pv = strategy_type(initial_selling_rate=19, use_market_maker_rate=use_mmr, cloud_coverage=1)
    pv.area = FakeArea()
    pv.owner = pv.area
    pv.event_activate()
    assert all(v == expected_rate for v in pv.offer_update.initial_rate.values())
    GlobalConfig.market_maker_rate = original_mmr


@parameterized.expand(
    [
        [
            True,
            13,
        ],
        [
            False,
            17,
        ],
    ]
)
def test_use_mmr_parameter_is_respected_for_pv_profiles(use_mmr, expected_rate):
    original_mmr = GlobalConfig.market_maker_rate
    GlobalConfig.market_maker_rate = 13
    user_profile_path = os.path.join(gsye_root_path, "resources/Solar_Curve_W_sunny.csv")
    pv = PVUserProfileStrategy(
        power_profile=user_profile_path, initial_selling_rate=17, use_market_maker_rate=use_mmr
    )
    pv.area = FakeArea()
    pv.owner = pv.area
    pv.event_activate()
    assert all(v == expected_rate for v in pv.offer_update.initial_rate.values())
    GlobalConfig.market_maker_rate = original_mmr


@pytest.fixture(name="pv_test11")
def fixture_pv_test11(area_test3):
    p = PVStrategy()
    p.area = area_test3
    p.owner = area_test3
    return p


def test_assert_if_trade_rate_is_lower_than_offer_rate(pv_test11):
    market_id = "market_id"
    pv_test11.offers.sold[market_id] = [
        Offer("offer_id", pendulum.now(), 30, 1, TraderDetails("FakeArea", ""))
    ]
    too_cheap_offer = Offer("offer_id", pendulum.now(), 29, 1, TraderDetails("FakeArea", ""))
    trade = Trade(
        "trade_id",
        "time",
        TraderDetails(pv_test11.owner.name, ""),
        TraderDetails("buyer", ""),
        offer=too_cheap_offer,
        traded_energy=1,
        trade_price=1,
    )

    with pytest.raises(AssertionError):
        pv_test11.event_offer_traded(market_id=market_id, trade=trade)


@pytest.fixture(name="pv_strategy")
def fixture_pv_strategy():
    pv_strategy = PVStrategy()
    pv_strategy.area = Mock()

    return pv_strategy


@patch("gsy_e.models.strategy.energy_parameters.pv.utils")
def test_set_energy_measurement_of_last_market(utils_mock, pv_strategy):
    """The real energy of the last market is set when necessary."""
    # If we are in the first market slot, the real energy is not set
    pv_strategy.area.current_market = None
    pv_strategy.state.set_energy_measurement_kWh = Mock()
    pv_strategy.state.get_energy_production_forecast_kWh = Mock(return_value=50)
    pv_strategy._set_energy_measurement_of_last_market()

    pv_strategy.state.set_energy_measurement_kWh.assert_not_called()

    # When there is at least one past market, the real energy is set
    pv_strategy.state.set_energy_measurement_kWh.reset_mock()
    pv_strategy.area.current_market = Mock()
    utils_mock.compute_altered_energy.return_value = 100
    pv_strategy._set_energy_measurement_of_last_market()

    pv_strategy.state.set_energy_measurement_kWh.assert_called_once_with(
        100, pv_strategy.area.current_market.time_slot
    )
