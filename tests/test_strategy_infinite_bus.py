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
import sys
import pendulum

from d3a.models.market.market_structures import Offer, Trade, BalancingOffer, Bid
from d3a.models.strategy.infinite_bus import InfiniteBusStrategy
from d3a.models.area import DEFAULT_CONFIG
from d3a.d3a_core.device_registry import DeviceRegistry
from d3a_interface.constants_limits import ConstSettings
from d3a.constants import TIME_ZONE

TIME = pendulum.today(tz=TIME_ZONE).at(hour=10, minute=45, second=0)


class FakeArea:
    def __init__(self, count):
        self.current_tick = 2
        self.appliance = None
        self.name = 'FakeArea'
        self.test_market = FakeMarket(0)
        self.test_balancing_market = FakeMarket(1)
        self.test_balancing_market_2 = FakeMarket(2)
        self._past_markets = {}
        self._bids = {}

    def get_future_market_from_id(self, id):
        return self.test_market

    @property
    def all_markets(self):
        return [self.test_market]

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
        self.id = count
        self.count = count
        self.created_offers = []
        self.created_balancing_offers = []
        self.sorted_offers = [Offer('id', 25., 1., 'other'), Offer('id', 26., 1., 'other')]
        self.traded_offers = []
        self._bids = {TIME: []}

    @property
    def time_slot(self):
        return TIME

    def offer(self, price, energy, seller, original_offer_price=None,
              seller_origin=None):
        offer = Offer('id', price, energy, seller)
        self.created_offers.append(offer)
        offer.id = 'id'
        return offer

    def balancing_offer(self, price, energy, seller):
        offer = BalancingOffer('id', price, energy, seller)
        self.created_balancing_offers.append(offer)
        offer.id = 'id'
        return offer

    def accept_offer(self, offer, buyer, *, energy=None, time=None, already_tracked=False,
                     trade_rate: float = None, trade_bid_info=None, buyer_origin=None):
        trade = Trade('trade_id', time, offer, offer.seller, buyer,
                      seller_origin=offer.seller_origin, buyer_origin=buyer_origin)
        self.traded_offers.append(trade)
        return trade

    def bid(self, price, energy, buyer, seller, original_bid_price=None,
            buyer_origin=None):
        bid = Bid("bid_id", price, energy, buyer, seller, buyer_origin=buyer_origin)
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
    bus_test1.event_activate()
    bus_test1.event_market_cycle()
    assert len(area_test1.test_balancing_market.created_balancing_offers) == 1
    assert len(area_test1.test_balancing_market_2.created_balancing_offers) == 1
    assert area_test1.test_balancing_market_2.created_balancing_offers[0].energy == \
        sys.maxsize
    assert area_test1.test_balancing_market_2.created_balancing_offers[0].price == \
        sys.maxsize * 50

    DeviceRegistry.REGISTRY = {}


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
    traded_offer = Offer(id='id', price=20, energy=1, seller='FakeArea',)
    bus_test2.event_trade(market_id=area_test2.test_market.id, trade=Trade(id='id',
                                                                           time='time',
                                                                           offer=traded_offer,
                                                                           seller='FakeArea',
                                                                           buyer='buyer'
                                                                           )
                          )
    assert len(area_test2.test_market.created_offers) == 1
    assert area_test2.test_market.created_offers[-1].energy == sys.maxsize


def test_on_offer_changed(area_test2, bus_test2):
    bus_test2.event_activate()
    existing_offer = Offer(id='id', price=20, energy=1, seller='FakeArea')
    new_offer = Offer(id='new_id', price=15, energy=0.75, seller='FakeArea')
    bus_test2.event_offer_changed(market_id=area_test2.test_market.id,
                                  existing_offer=existing_offer,
                                  new_offer=new_offer)
    assert existing_offer.id in bus_test2.offers.changed
    assert bus_test2.offers.changed[existing_offer.id] == new_offer


def test_event_trade_after_offer_changed_partial_offer(area_test2, bus_test2):
    existing_offer = Offer(id='old_id', price=20, energy=1, seller='FakeArea')
    new_offer = Offer(id='new_id', price=15, energy=0.75, seller='FakeArea')

    bus_test2.offers.post(existing_offer, area_test2.test_market)
    bus_test2.offers.post(new_offer, area_test2.test_market)
    bus_test2.event_offer_changed(market_id=area_test2.test_market.id,
                                  existing_offer=existing_offer,
                                  new_offer=new_offer)
    assert existing_offer.id in bus_test2.offers.changed
    assert bus_test2.offers.changed[existing_offer.id] == new_offer
    bus_test2.event_trade(market_id=area_test2.test_market.id,
                          trade=Trade(id='id',
                                      time='time',
                                      offer=existing_offer,
                                      seller='FakeArea',
                                      buyer='buyer')
                          )

    assert len(bus_test2.offers.posted) == 2
    assert new_offer in bus_test2.offers.posted
    assert bus_test2.offers.posted[new_offer] == area_test2.test_market.id
    assert len(bus_test2.offers.changed) == 0
    assert len(bus_test2.offers.sold) == 1
    assert existing_offer.id in bus_test2.offers.sold[area_test2.test_market.id]


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
    assert area_test3.test_market.created_offers[-1].price == 30 * sys.maxsize


"""TEST4"""


@pytest.fixture()
def area_test4():
    return FakeArea(0)


@pytest.fixture()
def bus_test4(area_test4):
    c = InfiniteBusStrategy(energy_sell_rate=30, energy_buy_rate=25)
    c.area = area_test4
    c.owner = area_test4
    return c


def testing_event_tick_buy_energy(bus_test4, area_test4):
    bus_test4.event_activate()
    bus_test4.event_tick()
    assert len(area_test4.test_market.traded_offers) == 1
    assert area_test4.test_market.traded_offers[-1].offer.energy == 1


def testing_event_market_cycle_posting_bids(bus_test4, area_test4):
    ConstSettings.IAASettings.MARKET_TYPE = 2
    bus_test4.event_activate()
    bus_test4.event_market_cycle()
    assert len(bus_test4._bids) == 1
    assert bus_test4._bids[area_test4.test_market.id][-1].energy == sys.maxsize
    assert bus_test4._bids[area_test4.test_market.id][-1].price == 25 * sys.maxsize
    ConstSettings.IAASettings.MARKET_TYPE = 1
