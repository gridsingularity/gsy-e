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
import pytest
import pendulum
import uuid
from pendulum import DateTime
from parameterized import parameterized
import os
from typing import Dict  # NOQA

from d3a.constants import TIME_ZONE
from d3a.models.area import DEFAULT_CONFIG
from d3a.models.market.market_structures import Offer, Trade
from d3a.models.strategy.pv import PVStrategy
from d3a.models.strategy.predefined_pv import PVPredefinedStrategy, PVUserProfileStrategy
from d3a_interface.constants_limits import ConstSettings, GlobalConfig
from d3a_interface.exceptions import D3ADeviceException
from d3a.constants import TIME_FORMAT
from d3a.d3a_core.util import d3a_path
from d3a.d3a_core.util import generate_market_slot_list


ENERGY_FORECAST = {}  # type: Dict[DateTime, float]
TIME = pendulum.today(tz=TIME_ZONE).at(hour=10, minute=45, second=0)


class FakeArea:
    def __init__(self):
        self.config = DEFAULT_CONFIG
        self.current_tick = 2
        self.name = 'FakeArea'
        self.test_market = FakeMarket(0)
        self._next_market = FakeMarket(0)

    def get_future_market_from_id(self, id):
        return self.test_market

    @property
    def current_market(self):
        return self.test_market

    def get_path_to_root_fees(self):
        return 0.

    @property
    def now(self) -> DateTime:
        """
        Return the 'current time' as a `DateTime` object.
        Can be overridden in subclasses to change the meaning of 'now'.

        In this default implementation 'current time' is defined by the number of ticks that
        have passed.
        """
        return DateTime.now(tz=TIME_ZONE).start_of('day') + (
            self.config.tick_length * self.current_tick
        )

    @property
    def all_markets(self):
        return [self.test_market,
                self.test_market,
                self.test_market]


class FakeAreaTimeSlot(FakeArea):
    def __init__(self):
        super().__init__()

    @property
    def all_markets(self):
        return [self._next_market]

    def create_next_market(self, time_slot):
        self._next_market = FakeMarketTimeSlot(time_slot)


class FakeMarketTimeSlot:
    def __init__(self, time_slot):
        self.time_slot = time_slot


class FakeMarket:
    def __init__(self, count):
        self.count = count
        self.id = str(count)
        self.created_offers = []
        self.offers = {'id': Offer(id='id', time=pendulum.now(), price=10, energy=0.5, seller='A')}

    def offer(self, price, energy, seller, original_offer_price=None, seller_origin=None):
        offer = Offer(str(uuid.uuid4()), pendulum.now(), price, energy, seller,
                      original_offer_price, seller_origin=seller_origin)
        self.created_offers.append(offer)
        self.offers[offer.id] = offer
        return offer

    @property
    def time_slot(self):
        return TIME

    @property
    def time_slot_str(self):
        return self.time_slot.format(TIME_FORMAT)

    def delete_offer(self, offer_id):
        return


class FakeTrade:
    def __init__(self, offer):
        self.offer = offer
        self.seller = "FakeSeller"

    @property
    def buyer(self):
        return "FakeBuyer"


"""TEST1"""


@pytest.fixture()
def area_test1():
    return FakeArea()


@pytest.fixture()
def pv_test1(area_test1):
    p = PVStrategy()
    p.area = area_test1
    p.owner = area_test1
    return p


def testing_activation(pv_test1):
    pv_test1.event_activate()
    global ENERGY_FORECAST
    ENERGY_FORECAST = pv_test1.energy_production_forecast_kWh


"""TEST2"""


@pytest.fixture()
def area_test2():
    return FakeArea()


@pytest.fixture()
def market_test2(area_test2):
    return area_test2.test_market


@pytest.fixture()
def pv_test2(area_test2):
    p = PVStrategy()
    p.area = area_test2
    p.owner = area_test2
    p.offers.posted = {}
    p.energy_production_forecast_kWh = ENERGY_FORECAST
    return p


@pytest.mark.skip('broken as event_tick does not decrease offer price with every tick')
def testing_event_tick(pv_test2, market_test2, area_test2):
    pv_test2.event_activate()
    pv_test2.event_tick()
    assert len(market_test2.created_offers) == 1
    assert len(pv_test2.offers.posted.items()) == 1
    offer_id1 = list(pv_test2.offers.posted.keys())[0]
    offer1 = market_test2.offers[offer_id1]
    assert market_test2.created_offers[0].price == \
        29.9 * pv_test2.energy_production_forecast_kWh[TIME]
    assert pv_test2.energy_production_forecast_kWh[
               pendulum.today(tz=TIME_ZONE).at(hour=0, minute=0, second=2)
           ] == 0
    area_test2.current_tick_in_slot = DEFAULT_CONFIG.ticks_per_slot - 2
    pv_test2.event_tick()
    offer_id2 = list(pv_test2.offers.posted.keys())[0]
    offer2 = market_test2.offers[offer_id2]
    assert offer1 != offer2
    assert len(pv_test2.offers.posted.items()) == 1
    # assert len(pv_test2.decrease_offer_price.calls) == 1


"""TEST 3"""


@pytest.fixture()
def area_test3():
    return FakeArea()


@pytest.fixture()
def market_test3(area_test3):
    return area_test3.test_market


@pytest.fixture()
def pv_test3(area_test3):
    p = PVStrategy()
    p.area = area_test3
    p.owner = area_test3
    p.offers.posted = {Offer('id', pendulum.now(), 1, 1, 'FakeArea'): area_test3.test_market.id}
    return p


def testing_decrease_offer_price(area_test3, pv_test3):
    assert len(pv_test3.offers.posted.items()) == 1
    pv_test3.event_activate()
    pv_test3.event_market_cycle()
    pv_test3.event_tick()
    for i in range(2):
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
    assert new_offer.price / new_offer.energy >= ConstSettings.PVSettings.SELLING_RATE_RANGE.final


"""TEST 4"""


@pytest.fixture()
def pv_test4(area_test3, called):
    p = PVStrategy()
    p.area = area_test3
    p.owner = area_test3
    p.offers.posted = {
        Offer(id='id', time=pendulum.now(), price=20,
              energy=1, seller='FakeArea'): area_test3.test_market.id
    }
    return p


def testing_event_trade(area_test3, pv_test4):
    pv_test4.state.available_energy_kWh[area_test3.test_market.time_slot] = 1
    pv_test4.event_trade(market_id=area_test3.test_market.id,
                         trade=Trade(id='id', time='time',
                                     offer=Offer(id='id', time=pendulum.now(), price=20,
                                                 energy=1, seller='FakeArea'),
                                     seller=area_test3.name, buyer='buyer'
                                     )
                         )
    assert len(pv_test4.offers.open) == 0


"""TEST 5"""


@pytest.fixture()
def pv_test5(area_test3, called):
    p = PVStrategy()
    p.area = area_test3
    p.owner = area_test3
    p.offers.posted = {'id': area_test3.test_market}
    return p


""" TEST 6"""


@pytest.fixture()
def pv_test6(area_test3):
    p = PVStrategy()
    p.area = area_test3
    p.owner = area_test3
    p.offers.posted = {}
    p.energy_production_forecast_kWh = ENERGY_FORECAST
    return p


@pytest.fixture()
def area_test66():
    return FakeAreaTimeSlot()


@pytest.fixture()
def pv_test66(area_test66):
    p = PVStrategy()
    p.area = area_test66
    p.owner = area_test66
    p.offers.posted = {}
    return p


def testing_produced_energy_forecast_real_data(pv_test66):

    pv_test66.event_activate()
    # prepare whole day of energy_production_forecast_kWh:
    for time_slot in generate_market_slot_list():
        pv_test66.area.create_next_market(time_slot)
        pv_test66.set_produced_energy_forecast_kWh_future_markets(reconfigure=False)
    morning_time = pendulum.today(tz=TIME_ZONE).at(hour=8, minute=20, second=0)
    afternoon_time = pendulum.today(tz=TIME_ZONE).at(hour=16, minute=40, second=0)

    class Counts(object):
        def __init__(self, time):
            self.total = 0
            self.count = 0
            self.time = time
    morning_counts = Counts('morning')
    afternoon_counts = Counts('afternoon')
    evening_counts = Counts('evening')
    for (time, power) in pv_test66.energy_production_forecast_kWh.items():
        if time < morning_time:
            morning_counts.total += 1
            morning_counts.count = morning_counts.count + 1 \
                if pv_test66.energy_production_forecast_kWh[time] == 0 else morning_counts.count
        elif morning_time < time < afternoon_time:
            afternoon_counts.total += 1
            afternoon_counts.count = afternoon_counts.count + 1 \
                if pv_test66.energy_production_forecast_kWh[time] > 0.001 \
                else afternoon_counts.count
        elif time > afternoon_time:
            evening_counts.total += 1
            evening_counts.count = evening_counts.count + 1 \
                if pv_test66.energy_production_forecast_kWh[time] == 0 else evening_counts.count

    total_count = morning_counts.total + afternoon_counts.total + evening_counts.total
    assert len(list(pv_test66.energy_production_forecast_kWh.items())) == total_count

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
    assert market_test3.created_offers[0].energy == pv_test6.energy_production_forecast_kWh[TIME]
    fake_trade = FakeTrade(market_test3.created_offers[0])
    fake_trade.seller = pv_test6.owner.name
    pv_test6.event_trade(market_id=market_test3.id, trade=fake_trade)
    market_test3.created_offers = []
    assert not market_test3.created_offers


def test_pv_constructor_rejects_incorrect_parameters():
    with pytest.raises(D3ADeviceException):
        PVStrategy(panel_count=-1)
    with pytest.raises(D3ADeviceException):
        PVStrategy(max_panel_power_W=-100)
    with pytest.raises(D3ADeviceException):
        pv = PVStrategy(initial_selling_rate=5, final_selling_rate=15)
        pv.event_activate()
    with pytest.raises(D3ADeviceException):
        PVStrategy(fit_to_limit=True, energy_rate_decrease_per_update=1)
    with pytest.raises(D3ADeviceException):
        PVStrategy(fit_to_limit=False, energy_rate_decrease_per_update=-1)


"""TEST7"""


@pytest.fixture()
def pv_test7(area_test3):
    p = PVStrategy(panel_count=1, initial_selling_rate=30)
    p.area = area_test3
    p.owner = area_test3
    p.offers.posted = {Offer('id', 1, 1, 'FakeArea'): area_test3.test_market.id}
    return p


"""TEST8"""


@pytest.fixture()
def pv_test8(area_test3):
    p = PVStrategy(panel_count=1, initial_selling_rate=30)
    p.area = area_test3
    p.owner = area_test3
    p.offers.posted = {Offer('id', pendulum.now(), 1, 1, 'FakeArea'): area_test3.test_market.id}
    return p


"""TEST9"""


@pytest.fixture()
def area_test9():
    return FakeArea()


@pytest.fixture()
def market_test9(area_test9):
    return area_test9.test_market


@pytest.fixture()
def pv_test9(area_test9):
    p = PVStrategy(panel_count=3)
    p.area = area_test9
    p.owner = area_test9
    p.offers.posted = {}
    p.energy_production_forecast_kWh = ENERGY_FORECAST
    return p


def testing_number_of_pv_sell_offers(pv_test9, market_test9, area_test9):
    pv_test9.event_activate()
    pv_test9.event_market_cycle()
    assert len(market_test9.created_offers) == len(area_test9.all_markets)


"""TEST10"""


@pytest.fixture()
def area_test10():
    return FakeArea()


@pytest.fixture
def market_test10():
    return FakeMarket(0)


@pytest.fixture()
def pv_strategy_test10(area_test10, called):
    s = PVStrategy(initial_selling_rate=25)
    s.owner = area_test10
    s.area = area_test10
    s.accept_offer = called
    return s


def test_initial_selling_rate(pv_strategy_test10, area_test10):
    pv_strategy_test10.event_activate()
    pv_strategy_test10.event_market_cycle()
    created_offer = area_test10.all_markets[0].created_offers[0]
    assert created_offer.price/created_offer.energy == 25


@parameterized.expand([
    [PVStrategy, True, 12, ],
    [PVStrategy, False, 19, ],
])
def test_use_mmr_parameter_is_respected1(strategy_type, use_mmr, expected_rate):
    GlobalConfig.market_maker_rate = 12
    pv = strategy_type(initial_selling_rate=19, use_market_maker_rate=use_mmr,
                       max_panel_power_W=200)
    pv.area = FakeArea()
    pv.owner = pv.area
    pv.event_activate()
    assert all(v == expected_rate for v in pv.offer_update.initial_rate.values())


@parameterized.expand([
    [PVPredefinedStrategy, True, 12, ],
    [PVPredefinedStrategy, False, 19, ],
])
def test_use_mmr_parameter_is_respected2(strategy_type, use_mmr, expected_rate):
    GlobalConfig.market_maker_rate = 12
    pv = strategy_type(initial_selling_rate=19, use_market_maker_rate=use_mmr,
                       cloud_coverage=1)
    pv.area = FakeArea()
    pv.owner = pv.area
    pv.event_activate()
    assert all(v == expected_rate for v in pv.offer_update.initial_rate.values())


@parameterized.expand([
    [True, 13, ],
    [False, 17, ],
])
def test_use_mmr_parameter_is_respected_for_pv_profiles(use_mmr, expected_rate):
    GlobalConfig.market_maker_rate = 13
    user_profile_path = os.path.join(d3a_path, "resources/Solar_Curve_W_sunny.csv")
    pv = PVUserProfileStrategy(
        power_profile=user_profile_path, initial_selling_rate=17, use_market_maker_rate=use_mmr)
    pv.area = FakeArea()
    pv.owner = pv.area
    pv.event_activate()
    assert all(v == expected_rate for v in pv.offer_update.initial_rate.values())


"""Test 11"""


@pytest.fixture()
def pv_test11(area_test3):
    p = PVStrategy()
    p.area = area_test3
    p.owner = area_test3
    return p


def test_assert_if_trade_rate_is_lower_than_offer_rate(pv_test11):
    market_id = "market_id"
    pv_test11.offers.sold[market_id] = [Offer("offer_id", pendulum.now(), 30, 1, "FakeArea")]
    to_cheap_offer = Offer("offer_id", pendulum.now(), 29, 1, "FakeArea")
    trade = Trade("trade_id", "time", to_cheap_offer, pv_test11, "buyer")

    with pytest.raises(AssertionError):
        pv_test11.event_trade(market_id=market_id, trade=trade)
