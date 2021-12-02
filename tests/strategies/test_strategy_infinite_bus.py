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
import os
import sys
from math import isclose
from uuid import uuid4

import pendulum
import pytest
from gsy_framework.constants_limits import ConstSettings, GlobalConfig

from gsy_e import constants
from gsy_e.constants import TIME_ZONE
from gsy_e.gsy_e_core.device_registry import DeviceRegistry
from gsy_e.gsy_e_core.util import d3a_path
from gsy_e.models.area import DEFAULT_CONFIG
from gsy_framework.data_classes import Offer, Trade, BalancingOffer, Bid
from gsy_e.models.strategy.infinite_bus import InfiniteBusStrategy

TIME = pendulum.today(tz=TIME_ZONE).at(hour=10, minute=45, second=0)


@pytest.fixture(scope="function", autouse=True)
def auto_fixture():
    constants.CONNECT_TO_PROFILES_DB = False
    GlobalConfig.market_maker_rate = ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE
    yield
    GlobalConfig.market_maker_rate = ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE
    ConstSettings.MASettings.MARKET_TYPE = 1
    ConstSettings.BalancingSettings.ENABLE_BALANCING_MARKET = False
    DeviceRegistry.REGISTRY = {}


class FakeArea:
    def __init__(self, count):
        self.current_tick = 2
        self.appliance = None
        self.name = 'FakeArea'
        self.uuid = str(uuid4())
        self.test_market = FakeMarket(0)
        self.test_balancing_market = FakeMarket(1)
        self.test_balancing_market_2 = FakeMarket(2)
        self._past_markets = {}
        self._bids = {}

    def get_future_market_from_id(self, id):
        return self.test_market

    @property
    def future_markets(self):
        return None

    @property
    def all_markets(self):
        return [self.test_market]

    @property
    def spot_market(self):
        return self.test_market

    @property
    def balancing_markets(self):
        return [self.test_balancing_market, self.test_balancing_market_2]

    @property
    def config(self):
        return DEFAULT_CONFIG

    @property
    def last_past_market(self):
        try:
            return list(self._past_markets.values())[-1]
        except IndexError:
            return None


class FakeMarket:
    def __init__(self, count):
        self.id = str(count)
        self.count = count
        self.created_offers = []
        self.created_balancing_offers = []
        self.sorted_offers = [Offer('id', pendulum.now(), 25., 1., 'other'),
                              Offer('id', pendulum.now(), 26., 1., 'other')]
        self.traded_offers = []
        self._bids = {TIME: []}

    @property
    def time_slot(self):
        return TIME

    def offer(self, price, energy, seller, original_price=None,
              seller_origin=None, seller_origin_id=None, seller_id=None,
              attributes=None, requirements=None, time_slot=None):
        offer = Offer("id", pendulum.now(), price, energy, seller, seller_origin=seller_origin,
                      seller_origin_id=seller_origin_id, seller_id=seller_id,
                      attributes=attributes, requirements=requirements, time_slot=time_slot)
        self.created_offers.append(offer)
        offer.id = "id"
        return offer

    def balancing_offer(self, price, energy, seller):
        offer = BalancingOffer('id', pendulum.now(), price, energy, seller)
        self.created_balancing_offers.append(offer)
        offer.id = 'id'
        return offer

    def accept_offer(self, offer_or_id, buyer, *, energy=None, time=None, already_tracked=False,
                     trade_rate: float = None, trade_bid_info=None, buyer_origin=None,
                     buyer_origin_id=None, buyer_id=None):
        offer = offer_or_id
        trade = Trade('trade_id', time, offer, offer.seller, buyer,
                      seller_origin=offer.seller_origin, buyer_origin=buyer_origin,
                      buyer_origin_id=buyer_origin_id, buyer_id=buyer_id)
        self.traded_offers.append(trade)
        return trade

    def bid(self, price, energy, buyer, original_price=None,
            buyer_origin=None, buyer_origin_id=None, buyer_id=None,
            attributes=None, requirements=None, time_slot=None):
        bid = Bid("bid_id", pendulum.now(), price, energy, buyer, buyer_origin=buyer_origin,
                  buyer_origin_id=buyer_origin_id, buyer_id=buyer_id,
                  attributes=attributes, requirements=requirements, time_slot=time_slot)
        return bid


"""COPY of CEP tests below"""
"""TEST1"""


@pytest.fixture()
def area_test1():
    return FakeArea(0)


@pytest.fixture()
def bus_test1(area_test1):
    c = InfiniteBusStrategy(energy_sell_rate=30)
    c.area = area_test1
    c.owner = area_test1
    return c


def test_global_market_maker_rate_set_at_instantiation(area_test1):
    strategy = InfiniteBusStrategy(energy_sell_rate=35)
    strategy.area = area_test1
    strategy.event_activate()
    for time, value in strategy.energy_rate.items():
        assert value == GlobalConfig.market_maker_rate[time]
    strategy = InfiniteBusStrategy(energy_rate_profile={"01:15": 40})
    strategy.area = area_test1
    strategy.event_activate()
    timestamp_key = pendulum.today("utc").set(hour=1, minute=15)
    assert GlobalConfig.market_maker_rate[timestamp_key] == 40


def testing_offer_is_created_at_first_market_not_on_activate(bus_test1, area_test1):
    bus_test1.event_activate()
    assert len(area_test1.test_market.created_offers) == 0
    bus_test1.event_market_cycle()
    assert len(area_test1.test_market.created_offers) == 1
    assert area_test1.test_market.created_offers[0].energy == sys.maxsize


def test_balancing_offers_are_not_sent_to_all_markets_if_device_not_in_registry(bus_test1,
                                                                                area_test1):
    DeviceRegistry.REGISTRY = {}
    bus_test1.event_activate()
    assert len(area_test1.test_balancing_market.created_balancing_offers) == 0


def test_balancing_offers_are_sent_to_all_markets_if_device_in_registry(bus_test1, area_test1):

    ConstSettings.BalancingSettings.ENABLE_BALANCING_MARKET = True
    DeviceRegistry.REGISTRY = {'FakeArea': (30, 40)}
    bus_test1.event_activate()
    bus_test1.event_market_cycle()
    assert len(area_test1.test_balancing_market.created_balancing_offers) == 1
    assert area_test1.test_balancing_market.created_balancing_offers[0].energy == sys.maxsize
    assert area_test1.test_balancing_market.created_balancing_offers[0].price == sys.maxsize * 40
    assert len(area_test1.test_balancing_market_2.created_balancing_offers) == 1
    assert area_test1.test_balancing_market_2.created_balancing_offers[0].energy == sys.maxsize
    assert area_test1.test_balancing_market_2.created_balancing_offers[0].price == sys.maxsize * 40

    DeviceRegistry.REGISTRY = {}


def test_event_market_cycle_does_not_create_balancing_offer_if_not_in_registry(
        bus_test1, area_test1):
    DeviceRegistry.REGISTRY = {}
    bus_test1.event_activate()
    bus_test1.event_market_cycle()
    assert len(area_test1.test_balancing_market.created_balancing_offers) == 0
    assert len(area_test1.test_balancing_market_2.created_balancing_offers) == 0


def test_event_market_cycle_creates_balancing_offer_on_last_market_if_in_registry(
        bus_test1, area_test1):
    DeviceRegistry.REGISTRY = {"FakeArea": (40, 50)}
    ConstSettings.BalancingSettings.ENABLE_BALANCING_MARKET = True
    bus_test1.event_activate()
    bus_test1.event_market_cycle()
    assert len(area_test1.test_balancing_market.created_balancing_offers) == 1
    assert len(area_test1.test_balancing_market_2.created_balancing_offers) == 1
    assert area_test1.test_balancing_market_2.created_balancing_offers[0].energy == \
        sys.maxsize
    assert area_test1.test_balancing_market_2.created_balancing_offers[0].price == \
        sys.maxsize * 50


"""TEST2"""


@pytest.fixture()
def area_test2():
    return FakeArea(0)


@pytest.fixture()
def bus_test2(area_test2):
    c = InfiniteBusStrategy(energy_sell_rate=30)
    c.area = area_test2
    c.owner = area_test2
    return c


def test_event_trade(area_test2, bus_test2):
    bus_test2.event_activate()
    bus_test2.event_market_cycle()
    traded_offer = Offer(
        id="id", creation_time=pendulum.now(), price=20, energy=1, seller="FakeArea",)
    bus_test2.event_offer_traded(market_id=area_test2.test_market.id,
                                 trade=Trade(id="id",
                                             creation_time="time",
                                             offer_bid=traded_offer,
                                             seller="FakeArea",
                                             buyer="buyer"
                                             )
                                 )
    assert len(area_test2.test_market.created_offers) == 1
    assert area_test2.test_market.created_offers[-1].energy == sys.maxsize


def test_on_offer_changed(area_test2, bus_test2):
    bus_test2.event_activate()
    original_offer = Offer(
        id='id', creation_time=pendulum.now(), price=20, energy=1, seller='FakeArea')
    accepted_offer = Offer(
        id='new', creation_time=pendulum.now(), price=15, energy=0.75, seller='FakeArea')
    residual_offer = Offer(id='new_id', creation_time=pendulum.now(), price=5,
                           energy=0.25, seller='FakeArea')
    bus_test2.event_offer_split(market_id=area_test2.test_market.id,
                                original_offer=original_offer,
                                accepted_offer=accepted_offer,
                                residual_offer=residual_offer)
    assert original_offer.id in bus_test2.offers.split
    assert bus_test2.offers.split[original_offer.id] == accepted_offer


def test_event_trade_after_offer_changed_partial_offer(area_test2, bus_test2):
    original_offer = Offer(id="old_id", creation_time=pendulum.now(),
                           price=20, energy=1, seller="FakeArea")
    accepted_offer = Offer(id="old_id", creation_time=pendulum.now(),
                           price=15, energy=0.75, seller="FakeArea")
    residual_offer = Offer(id="res_id", creation_time=pendulum.now(),
                           price=5, energy=0.25, seller="FakeArea")
    bus_test2.offers.post(original_offer, area_test2.test_market.id)
    bus_test2.event_offer_split(market_id=area_test2.test_market.id,
                                original_offer=original_offer,
                                accepted_offer=accepted_offer,
                                residual_offer=residual_offer)
    assert original_offer.id in bus_test2.offers.split
    assert bus_test2.offers.split[original_offer.id] == accepted_offer
    bus_test2.event_offer_traded(market_id=area_test2.test_market.id,
                                 trade=Trade(id="id",
                                             creation_time="time",
                                             offer_bid=original_offer,
                                             seller="FakeArea",
                                             buyer="buyer")
                                 )

    assert residual_offer in bus_test2.offers.posted
    assert bus_test2.offers.posted[residual_offer] == area_test2.test_market.id
    assert len(bus_test2.offers.posted) == 1
    assert len(bus_test2.offers.split) == 1
    assert len(bus_test2.offers.sold) == 1
    assert original_offer in bus_test2.offers.sold_in_market(area_test2.test_market.id)


def test_validate_posted_offers_get_updated_on_offer_energy_method(area_test2, bus_test2):
    bus_test2.event_activate()
    bus_test2.offer_energy(area_test2.test_market)
    assert len(bus_test2.offers.posted) == 1
    assert list(bus_test2.offers.posted.values())[0] == area_test2.test_market.id


"""COPY of CEP tests above"""


"""TEST3"""


@pytest.fixture()
def area_test3():
    return FakeArea(0)


@pytest.fixture()
def bus_test3(area_test3):
    c = InfiniteBusStrategy(energy_sell_rate=30)
    c.area = area_test3
    c.owner = area_test3
    return c


def testing_event_market_cycle_post_offers(bus_test3, area_test3):
    bus_test3.event_activate()
    bus_test3.event_market_cycle()
    assert len(area_test3.test_market.created_offers) == 1
    assert area_test3.test_market.created_offers[-1].energy == sys.maxsize
    assert area_test3.test_market.created_offers[-1].price == float(30 * sys.maxsize)


"""TEST4"""


@pytest.fixture()
def bus_test4(area_test1):
    c = InfiniteBusStrategy(energy_sell_rate=30, energy_buy_rate=25)
    c.area = area_test1
    c.owner = area_test1
    return c


def testing_event_tick_buy_energy(bus_test4, area_test1):
    bus_test4.event_activate()
    bus_test4.event_tick()
    assert len(area_test1.test_market.traded_offers) == 1
    assert area_test1.test_market.traded_offers[-1].offer_bid.energy == 1


def testing_event_market_cycle_posting_bids(bus_test4, area_test1):
    ConstSettings.MASettings.MARKET_TYPE = 2
    bus_test4.event_activate()
    bus_test4.event_market_cycle()
    assert len(bus_test4._bids) == 1
    assert bus_test4._bids[area_test1.test_market.id][-1].energy == sys.maxsize
    assert isclose(bus_test4._bids[area_test1.test_market.id][-1].price, 25 * sys.maxsize)


def test_global_market_maker_rate_single_value(bus_test4):
    assert isinstance(GlobalConfig.market_maker_rate, dict)
    assert all(
        v == ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE
        for v in GlobalConfig.market_maker_rate.values())


"""TEST5"""


@pytest.fixture()
def bus_test5(area_test1):
    c = InfiniteBusStrategy(
        energy_rate_profile=os.path.join(d3a_path, "resources", "SAM_SF_Summer.csv"))
    c.area = area_test1
    c.owner = area_test1
    yield c


def test_global_market_maker_rate_profile_and_infinite_bus_selling_rate_profile(bus_test5):
    assert isinstance(GlobalConfig.market_maker_rate, dict)
    assert len(GlobalConfig.market_maker_rate) == 96
    assert list(GlobalConfig.market_maker_rate.values())[0] == 516.0
    assert list(GlobalConfig.market_maker_rate.values())[-1] == 595.0
    bus_test5.event_activate()
    assert list(bus_test5.energy_rate.values())[0] == 516.0
    assert list(bus_test5.energy_rate.values())[-1] == 595.0


"""TEST6"""


@pytest.fixture()
def bus_test6(area_test1):
    c = InfiniteBusStrategy(
        buying_rate_profile=os.path.join(d3a_path, "resources", "LOAD_DATA_1.csv"))
    c.area = area_test1
    c.owner = area_test1
    yield c


def test_infinite_bus_buying_rate_set_as_profile(bus_test6):
    bus_test6.event_activate()
    assert isinstance(bus_test6.energy_buy_rate, dict)
    assert len(bus_test6.energy_buy_rate) == 96
    assert list(bus_test6.energy_buy_rate.values())[0] == 10
    assert list(bus_test6.energy_buy_rate.values())[15] == 15
