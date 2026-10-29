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

from uuid import uuid4

import pendulum
import pytest
from gsy_framework.constants_limits import ConstSettings, GlobalConfig
from gsy_framework.constants_limits import TIME_ZONE, TIME_FORMAT
from gsy_framework.data_classes import Offer, Trade, BalancingOffer, TraderDetails

from gsy_e.gsy_e_core.device_registry import DeviceRegistry
from gsy_e.gsy_e_core.util import change_global_config
from gsy_e.models.config import create_simulation_config_from_global_config
from gsy_e.models.strategy import INF_ENERGY
from gsy_e.models.strategy.commercial_producer import CommercialStrategy
from gsy_e.models.strategy.market_maker_strategy import MarketMakerStrategy

TIME = pendulum.today(tz=TIME_ZONE).at(hour=10, minute=45, second=0)

DEFAULT_CONFIG = create_simulation_config_from_global_config()


@pytest.fixture(scope="module", autouse=True)
def auto_fixture():
    """
    Module scope fixture that reverts the market maker rate value to the default one, and
    disables the balancing market.
    """
    default_mmr = GlobalConfig.market_maker_rate
    change_global_config(**DEFAULT_CONFIG.__dict__)
    yield
    ConstSettings.BalancingSettings.ENABLE_BALANCING_MARKET = False
    GlobalConfig.market_maker_rate = default_mmr


class FakeArea:
    """Fake class that mimics the Area class."""

    # pylint: disable=too-many-instance-attributes,missing-function-docstring
    def __init__(self, _count):
        self.current_tick = 2
        self.name = "FakeArea"
        self.uuid = str(uuid4())
        self.test_market = FakeMarket(0)
        self.test_balancing_market = FakeMarket(1)
        self.test_balancing_market_2 = FakeMarket(2)
        self._past_markets = {}

    def get_future_market_from_id(self, _id):
        return self.test_market

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
    """Fake class that mimics the Market class."""

    # pylint: disable=missing-function-docstring,too-many-arguments
    def __init__(self, count):
        self.id = str(count)
        self.count = count
        self.created_offers = []
        self.created_balancing_offers = []

    def offer(self, price, energy, seller, original_price=None):
        offer = Offer("id", pendulum.now(), price, energy, seller, original_price)
        self.created_offers.append(offer)
        offer.id = "id"
        return offer

    def balancing_offer(self, price, energy, seller):
        offer = BalancingOffer("id", pendulum.now(), price, energy, seller)
        self.created_balancing_offers.append(offer)
        offer.id = "id"
        return offer

    @property
    def time_slot(self):
        return TIME

    @property
    def time_slot_str(self):
        return self.time_slot.format(TIME_FORMAT)


@pytest.fixture(name="area_test1")
def fixture_area_test1():
    return FakeArea(0)


@pytest.fixture(name="commercial_test1")
def fixture_commercial_test1(area_test1):
    c = CommercialStrategy(energy_rate=30)
    c.area = area_test1
    c.owner = area_test1
    return c


def test_offer_is_created_at_first_market_not_on_activate(commercial_test1, area_test1):
    commercial_test1.event_activate()
    assert len(area_test1.test_market.created_offers) == 0
    commercial_test1.event_market_cycle()
    assert len(area_test1.test_market.created_offers) == 1
    assert area_test1.test_market.created_offers[0].energy == INF_ENERGY


def test_balancing_offers_are_not_sent_to_all_markets_if_device_not_in_registry(
    commercial_test1, area_test1
):
    DeviceRegistry.REGISTRY = {}
    commercial_test1.event_activate()
    assert len(area_test1.test_balancing_market.created_balancing_offers) == 0


def test_balancing_offers_are_sent_to_all_markets_if_device_in_registry(
    commercial_test1, area_test1
):

    ConstSettings.BalancingSettings.ENABLE_BALANCING_MARKET = True
    DeviceRegistry.REGISTRY = {"FakeArea": (30, 40)}
    commercial_test1.event_activate()
    commercial_test1.event_market_cycle()
    assert len(area_test1.test_balancing_market.created_balancing_offers) == 1
    assert area_test1.test_balancing_market.created_balancing_offers[0].energy == INF_ENERGY
    assert area_test1.test_balancing_market.created_balancing_offers[0].price == INF_ENERGY * 40
    assert len(area_test1.test_balancing_market_2.created_balancing_offers) == 1
    assert area_test1.test_balancing_market_2.created_balancing_offers[0].energy == INF_ENERGY
    assert area_test1.test_balancing_market_2.created_balancing_offers[0].price == INF_ENERGY * 40

    DeviceRegistry.REGISTRY = {}


def test_event_market_cycle_does_not_create_balancing_offer_if_not_in_registry(
    commercial_test1, area_test1
):
    DeviceRegistry.REGISTRY = {}
    commercial_test1.event_activate()
    commercial_test1.event_market_cycle()
    assert len(area_test1.test_balancing_market.created_balancing_offers) == 0
    assert len(area_test1.test_balancing_market_2.created_balancing_offers) == 0


def test_event_market_cycle_creates_balancing_offer_on_last_market_if_in_registry(
    commercial_test1, area_test1
):
    ConstSettings.BalancingSettings.ENABLE_BALANCING_MARKET = True
    DeviceRegistry.REGISTRY = {"FakeArea": (40, 50)}
    commercial_test1.event_activate()
    commercial_test1.event_market_cycle()
    assert len(area_test1.test_balancing_market.created_balancing_offers) == 1
    assert len(area_test1.test_balancing_market_2.created_balancing_offers) == 1
    assert area_test1.test_balancing_market_2.created_balancing_offers[0].energy == INF_ENERGY
    assert area_test1.test_balancing_market_2.created_balancing_offers[0].price == INF_ENERGY * 50

    DeviceRegistry.REGISTRY = {}


@pytest.fixture(name="area_test2")
def fixture_area_test2():
    return FakeArea(0)


@pytest.fixture(name="commercial_test2")
def fixture_commercial_test2(area_test2):
    c = CommercialStrategy(energy_rate=30)
    c.area = area_test2
    c.owner = area_test2
    return c


def test_event_trade(area_test2, commercial_test2):
    commercial_test2.event_activate()
    commercial_test2.event_market_cycle()
    traded_offer = Offer(
        id="id",
        creation_time=pendulum.now(),
        price=20,
        energy=1,
        seller=TraderDetails("FakeArea", ""),
    )
    commercial_test2.event_offer_traded(
        market_id=area_test2.test_market.id,
        trade=Trade(
            id="id",
            offer=traded_offer,
            creation_time=pendulum.now(),
            seller=TraderDetails("FakeArea", ""),
            buyer=TraderDetails("buyer", ""),
            traded_energy=1,
            trade_price=1,
        ),
    )
    assert len(area_test2.test_market.created_offers) == 1
    assert area_test2.test_market.created_offers[-1].energy == INF_ENERGY


def test_on_offer_split(area_test2, commercial_test2):
    commercial_test2.event_activate()
    original_offer = Offer(
        id="id",
        creation_time=pendulum.now(),
        price=20,
        energy=1,
        seller=TraderDetails("FakeArea", ""),
    )
    accepted_offer = Offer(
        id="new_id",
        creation_time=pendulum.now(),
        price=15,
        energy=0.75,
        seller=TraderDetails("FakeArea", ""),
    )
    residual_offer = Offer(
        id="res_id",
        creation_time=pendulum.now(),
        price=55,
        energy=0.25,
        seller=TraderDetails("FakeArea", ""),
    )
    commercial_test2.offers.post(original_offer, area_test2.test_market.id)
    commercial_test2.event_offer_split(
        market_id=area_test2.test_market.id,
        original_offer=original_offer,
        accepted_offer=accepted_offer,
        residual_offer=residual_offer,
    )
    assert original_offer.id in commercial_test2.offers.split
    assert commercial_test2.offers.split[original_offer.id] == accepted_offer


def test_event_trade_after_offer_changed_partial_offer(area_test2, commercial_test2):
    original_offer = Offer(
        id="old_id",
        creation_time=pendulum.now(),
        price=20,
        energy=1,
        seller=TraderDetails("FakeArea", ""),
    )
    accepted_offer = Offer(
        id="old_id",
        creation_time=pendulum.now(),
        price=15,
        energy=0.75,
        seller=TraderDetails("FakeArea", ""),
    )
    residual_offer = Offer(
        id="res_id",
        creation_time=pendulum.now(),
        price=5,
        energy=0.25,
        seller=TraderDetails("FakeArea", ""),
    )
    commercial_test2.offers.post(original_offer, area_test2.test_market.id)
    commercial_test2.event_offer_split(
        market_id=area_test2.test_market.id,
        original_offer=original_offer,
        accepted_offer=accepted_offer,
        residual_offer=residual_offer,
    )
    assert original_offer.id in commercial_test2.offers.split
    assert commercial_test2.offers.split[original_offer.id] == accepted_offer
    commercial_test2.event_offer_traded(
        market_id=area_test2.test_market.id,
        trade=Trade(
            id="id",
            offer=original_offer,
            creation_time=pendulum.now(),
            seller=TraderDetails("FakeArea", ""),
            buyer=TraderDetails("buyer", ""),
            traded_energy=1,
            trade_price=1,
        ),
    )

    assert residual_offer in commercial_test2.offers.posted
    assert commercial_test2.offers.posted[residual_offer] == area_test2.test_market.id
    assert len(commercial_test2.offers.posted) == 1
    assert len(commercial_test2.offers.split) == 1
    assert len(commercial_test2.offers.sold) == 1
    assert original_offer in commercial_test2.offers.sold_in_market(area_test2.test_market.id)


def test_validate_posted_offers_get_updated_on_offer_energy_method(area_test2, commercial_test2):
    commercial_test2.event_activate()
    commercial_test2.offer_energy(area_test2.test_market)
    assert len(commercial_test2.offers.posted) == 1
    assert list(commercial_test2.offers.posted.values())[0] == area_test2.test_market.id


@pytest.fixture(name="area_test3")
def fixture_area_test3():
    return FakeArea(0)


@pytest.fixture(name="commercial_test3")
def fixture_commercial_test3(area_test3):
    c = CommercialStrategy(energy_rate=30)
    c.area = area_test3
    c.owner = area_test3
    return c


def test_event_market_cycle(commercial_test3, area_test3):
    commercial_test3.event_activate()
    commercial_test3.event_market_cycle()
    assert len(area_test3.test_market.created_offers) == 1
    assert area_test3.test_market.created_offers[-1].energy == INF_ENERGY


# TODO: Re-add test once validator is implemented in gsy-framework
# def test_commercial_producer_constructor_rejects_invalid_parameters():
#    with pytest.raises(ValueError):
#        CommercialStrategy(energy_rate=-1)


def test_market_maker_strategy_constructor_modifies_global_market_maker_rate():
    # pylint: disable=no-member
    MarketMakerStrategy(energy_rate=22)
    assert all(v == 22 for v in GlobalConfig.market_maker_rate.values())
