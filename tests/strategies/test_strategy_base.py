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

# pylint: disable=missing-function-docstring, protected-access, missing-class-docstring
# pylint: disable=no-self-use, redefined-builtin, unused-argument, too-many-arguments
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pendulum
import pytest
from gsy_framework.constants_limits import ConstSettings
from gsy_framework.data_classes import Bid, Offer, Trade, TraderDetails
from gsy_framework.enums import SpotMarketTypeEnum

from gsy_framework.constants_limits import TIME_ZONE
from gsy_e.gsy_e_core.blockchain_interface import NonBlockchainInterface
from gsy_e.gsy_e_core.exceptions import MarketException
from gsy_e.models.market.one_sided import OneSidedMarket
from gsy_e.models.market.two_sided import TwoSidedMarket
from gsy_e.models.strategy import BaseStrategy, BidEnabledStrategy, Offers


def teardown_function():
    ConstSettings.MASettings.MARKET_TYPE = 1


class FakeLog:
    def warning(self, *args):
        pass

    def error(self, *args):
        pass


class FakeOwner:

    def __init__(self):
        self.uuid = str(uuid4())

    @property
    def name(self):
        return "FakeOwner"


class FakeArea:
    def __init__(self, market=None):
        self._market = market
        self.uuid = str(uuid4())

    def get_spot_or_future_market_by_id(self, _):
        return self._market

    def is_market_future(self, _):
        return False

    def is_market_settlement(self, _):
        return False

    @property
    def name(self):
        return "FakeArea"


class FakeStrategy:
    @property
    def owner(self):
        return FakeOwner()

    @property
    def area(self):
        return FakeOwner()

    @property
    def log(self):
        return FakeLog()


class FakeOffer:
    def __init__(self, id):
        self.id = id


class FakeMarket:
    def __init__(self, *, raises, id="11"):
        self.raises = raises
        self.transfer_fee_ratio = 0
        self.bids = {}
        self.id = id
        self.time_slot = pendulum.now()

    def accept_offer(self, offer_or_id, *, buyer="", energy=None, time=None, trade_bid_info=None):
        offer = offer_or_id
        if self.raises:
            raise MarketException

        if energy is None:
            energy = offer.energy
        offer.energy = energy
        return Trade(
            "trade",
            0,
            offer.seller,
            TraderDetails("FakeOwner", ""),
            offer=offer,
            traded_energy=offer.energy,
            trade_price=offer.price,
        )

    def bid(self, price, energy, buyer, original_price=None, time_slot=None):
        return Bid(123, pendulum.now(), price, energy, buyer, original_price, time_slot=time_slot)


@pytest.fixture(name="offers")
def offers_fixture():
    market = FakeMarket(raises=False, id="market")
    fixture = Offers(FakeStrategy())
    fixture.post(FakeOffer("id"), market.id)
    fixture.__fake_market = market
    return fixture


def test_offers_open(offers):
    assert len(offers.open) == 1
    market = offers.__fake_market
    old_offer = offers.posted_in_market(market.id)[0]
    offers.sold_offer(old_offer, "market")
    assert len(offers.open) == 0


def test_offers_replace_open_offer(offers):
    market = offers.__fake_market
    old_offer = offers.posted_in_market(market.id)[0]
    new_offer = FakeOffer("new_id")
    offers.replace(old_offer, new_offer, market.id)
    assert offers.posted_in_market(market.id)[0].id == "new_id"
    assert "id" not in offers.posted


def test_offers_does_not_replace_sold_offer(offers):
    old_offer = offers.posted_in_market("market")[0]
    new_offer = FakeOffer("new_id")
    offers.sold_offer(old_offer, "market")
    offers.replace(old_offer, new_offer, "market")
    assert old_offer in offers.posted and new_offer not in offers.posted


@pytest.fixture(name="offers2")
def offers2_fixture():
    fixture = Offers(FakeStrategy())
    fixture.post(FakeOffer("id"), "market")
    fixture.post(FakeOffer("id2"), "market")
    fixture.post(FakeOffer("id3"), "market2")
    return fixture


def test_offers_in_market(offers2):
    old_offer = next(o for o in offers2.posted_in_market("market") if o.id == "id2")
    assert len(offers2.posted_in_market("market")) == 2
    offers2.sold_offer(old_offer, "market")
    assert len(offers2.sold_in_market("market")) == 1
    assert len(offers2.sold_in_market("market2")) == 0


@pytest.fixture(name="offer1")
def offer1_fixture():
    return Offer("id", pendulum.now(), 1, 3, TraderDetails("FakeOwner", ""))


@pytest.fixture(name="offers3")
def offers3_fixture(offer1):
    fixture = Offers(FakeStrategy())
    fixture.post(offer1, "market")
    fixture.post(Offer("id2", pendulum.now(), 1, 1, TraderDetails("FakeOwner", "")), "market")
    fixture.post(Offer("id3", pendulum.now(), 1, 1, TraderDetails("FakeOwner", "")), "market2")
    return fixture


def test_offers_partial_offer(offer1, offers3):
    accepted_offer = Offer("id", pendulum.now(), 1, 0.6, offer1.seller)
    residual_offer = Offer("new_id", pendulum.now(), 1, 1.2, offer1.seller)
    offers3.on_offer_split(offer1, accepted_offer, residual_offer, "market")
    trade = Trade(
        "trade_id",
        pendulum.now(tz=TIME_ZONE),
        offer1.seller,
        TraderDetails("buyer", ""),
        offer=accepted_offer,
        traded_energy=0.6,
        trade_price=1,
    )
    offers3.on_trade("market", trade)
    assert len(offers3.sold_in_market("market")) == 1
    assert accepted_offer in offers3.sold_in_market("market")


@pytest.fixture(name="offer_to_accept")
def offer_to_accept_fixture():
    return Offer("new", pendulum.now(), 1.0, 0.5, TraderDetails("someone", ""))


@pytest.fixture(name="base")
def base_strategy_fixture():
    base = BidEnabledStrategy()
    base.owner = FakeOwner()
    base.area = FakeArea()
    return base


def test_accept_offer(base, offer_to_accept):
    market = FakeMarket(raises=False)
    base.accept_offer(market, offer_to_accept)
    assert offer_to_accept in base.offers.bought.keys()
    assert market.id == base.offers.bought[offer_to_accept]


def test_accept_partial_offer(base, offer_to_accept):
    market = FakeMarket(raises=False)
    base.accept_offer(market, offer_to_accept, energy=0.1)

    assert list(base.offers.bought.keys())[0].energy == 0.1


def test_accept_offer_handles_market_exception(base, offer_to_accept):
    market = FakeMarket(raises=True)
    try:
        base.accept_offer(market, offer_to_accept, energy=0.5)
    except MarketException:
        pass
    assert len(base.offers.bought.keys()) == 0


@patch(
    "gsy_framework.constants_limits.ConstSettings.MASettings.MARKET_TYPE",
    SpotMarketTypeEnum.TWO_SIDED.value,
)
def test_accept_post_bid(base):
    market = FakeMarket(raises=True)

    bid = base.post_bid(market, 10, 5)
    assert base.are_bids_posted(market.id)
    assert len(base.get_posted_bids(market)) == 1
    assert base.get_posted_bids(market)[0] == bid
    assert bid.energy == 5
    assert bid.price == 10
    assert bid.buyer.name == "FakeOwner"


@patch(
    "gsy_framework.constants_limits.ConstSettings.MASettings.MARKET_TYPE",
    SpotMarketTypeEnum.TWO_SIDED.value,
)
def test_remove_bid_from_pending(base):
    market = FakeMarket(raises=True)
    base.area._market = market
    bid = base.post_bid(market, 10, 5)
    assert base.are_bids_posted(market.id)

    base.remove_bid_from_pending(market.id, bid.id)
    assert not base.are_bids_posted(market.id)


@patch(
    "gsy_framework.constants_limits.ConstSettings.MASettings.MARKET_TYPE",
    SpotMarketTypeEnum.TWO_SIDED.value,
)
def test_add_bid_to_bought(base):
    market = FakeMarket(raises=True)
    base.area._market = market
    bid = base.post_bid(market, 10, 5)
    assert base.are_bids_posted(market.id)

    base.add_bid_to_bought(bid, market.id)
    assert not base.are_bids_posted(market.id)
    assert len(base._get_traded_bids_from_market(market.id)) == 1
    assert base._get_traded_bids_from_market(market.id) == [bid]


def test_bid_events_fail_for_one_sided_market(base):
    ConstSettings.MASettings.MARKET_TYPE = 1
    test_bid = Bid("123", pendulum.now(), 12, 23, TraderDetails("A", ""))
    with pytest.raises(AssertionError):
        base.event_bid_traded(market_id=123, bid_trade=test_bid)
    with pytest.raises(AssertionError):
        base.event_bid_deleted(market_id=123, bid=test_bid)
    with pytest.raises(AssertionError):
        base.event_bid_split(
            market_id=123, original_bid=test_bid, accepted_bid=test_bid, residual_bid=test_bid
        )


def test_bid_deleted_removes_bid_from_posted(base):
    ConstSettings.MASettings.MARKET_TYPE = 2
    test_bid = Bid("123", pendulum.now(), 12, 23, TraderDetails(base.owner.name, ""))
    market = FakeMarket(raises=False, id=21)
    base.area._market = market
    base._bids[market.id] = [test_bid]
    base.event_bid_deleted(market_id=21, bid=test_bid)
    assert base.get_posted_bids(market) == []


def test_bid_split_adds_bid_to_posted(base):
    ConstSettings.MASettings.MARKET_TYPE = 2
    test_bid = Bid("123", pendulum.now(), 12, 12, TraderDetails(base.owner.name, ""))
    accepted_bid = Bid("123", pendulum.now(), 8, 8, TraderDetails(base.owner.name, ""))
    residual_bid = Bid("456", pendulum.now(), 4, 4, TraderDetails(base.owner.name, ""))
    market = FakeMarket(raises=False, id=21)
    base.area._market = market
    base._bids[market.id] = []
    base.event_bid_split(
        market_id=21, original_bid=test_bid, accepted_bid=accepted_bid, residual_bid=residual_bid
    )
    assert base.get_posted_bids(market) == [accepted_bid, residual_bid]


def test_bid_traded_moves_bid_from_posted_to_traded(base):
    ConstSettings.MASettings.MARKET_TYPE = 2
    test_bid = Bid("123", pendulum.now(), 12, 23, TraderDetails(base.owner.name, ""))
    trade = MagicMock()
    trade.buyer.name = base.owner.name
    trade.match_details = {"bid": test_bid, "offer": None}
    market = FakeMarket(raises=False, id=21)
    base.area._market = market
    base._bids[market.id] = [test_bid]
    base.event_bid_traded(market_id=21, bid_trade=trade)
    assert base.get_posted_bids(market) == []
    assert base._get_traded_bids_from_market(market.id) == [test_bid]


def test_trades_returns_market_trades(base):
    test_trades = [
        Trade(
            "123",
            pendulum.now(),
            TraderDetails(base.owner.name, ""),
            TraderDetails("buyer", ""),
            10,
            5,
        ),
        Trade(
            "123",
            pendulum.now(),
            TraderDetails("seller", ""),
            TraderDetails(base.owner.name, ""),
            11,
            6,
        ),
        Trade(
            "123", pendulum.now(), TraderDetails("seller", ""), TraderDetails("buyer", ""), 12, 7
        ),
        Trade(
            "123",
            pendulum.now(),
            TraderDetails(base.owner.name, ""),
            TraderDetails("buyer", ""),
            13,
            8,
        ),
    ]
    market = FakeMarket(raises=False, id=21)
    # pylint: disable=attribute-defined-outside-init
    market.trades = test_trades
    base.area._market = market
    trade_list = list(base.trades[market])
    assert len(trade_list) == 3
    assert trade_list[0] == test_trades[0]
    assert trade_list[1] == test_trades[1]
    assert trade_list[2] == test_trades[3]


@pytest.mark.parametrize("market_class", [OneSidedMarket, TwoSidedMarket])
def test_can_offer_be_posted(market_class):
    base = BaseStrategy()
    base.owner = FakeOwner()
    base.area = FakeArea()

    time_slot = pendulum.now(tz=TIME_ZONE)
    market = market_class(time_slot=time_slot)

    base.offers.post(
        Offer(
            "id",
            time_slot.add(seconds=1),
            price=1,
            energy=12,
            seller=TraderDetails("A", ""),
            time_slot=time_slot,
        ),
        market.id,
    )
    base.offers.post(
        Offer(
            "id2",
            time_slot.add(seconds=2),
            price=1,
            energy=13,
            seller=TraderDetails("A", ""),
            time_slot=time_slot,
        ),
        market.id,
    )
    base.offers.post(
        Offer(
            "id3",
            time_slot.add(seconds=3),
            price=1,
            energy=20,
            seller=TraderDetails("A", ""),
            time_slot=time_slot,
        ),
        market.id,
    )

    assert base.can_offer_be_posted(4.999, 1, 50, market, time_slot=None) is True
    assert base.can_offer_be_posted(5.0, 1, 50, market, time_slot=None) is True
    assert base.can_offer_be_posted(5.001, 1, 50, market, time_slot=None) is False

    assert base.can_offer_be_posted(4.999, 1, 50, market, time_slot=time_slot) is True
    assert base.can_offer_be_posted(5.0, 1, 50, market, time_slot=time_slot) is True
    assert base.can_offer_be_posted(5.001, 1, 50, market, time_slot=time_slot) is False

    assert (
        base.can_offer_be_posted(5.001, 1, 50, market, time_slot=time_slot, replace_existing=True)
        is True
    )
    assert (
        base.can_offer_be_posted(50, 1, 50, market, time_slot=time_slot, replace_existing=True)
        is True
    )
    assert (
        base.can_offer_be_posted(50.001, 1, 50, market, time_slot=time_slot, replace_existing=True)
        is False
    )


@pytest.mark.parametrize("market_class", [TwoSidedMarket])
@patch(
    "gsy_framework.constants_limits.ConstSettings.MASettings.MARKET_TYPE",
    SpotMarketTypeEnum.TWO_SIDED.value,
)
def test_can_bid_be_posted(market_class, base):
    market = market_class(time_slot=pendulum.now())

    base.post_bid(market, price=1, energy=23, replace_existing=False)
    base.post_bid(market, price=1, energy=27, replace_existing=False)
    base.post_bid(market, price=1, energy=10, replace_existing=False)

    assert base.can_bid_be_posted(9.999, 1, 70, market, replace_existing=False) is True
    assert base.can_bid_be_posted(10.0, 1, 70, market, replace_existing=False) is True
    assert base.can_bid_be_posted(10.001, 1, 70, market, replace_existing=False) is False

    assert base.can_bid_be_posted(10.001, 1, 70, market, replace_existing=True) is True
    assert base.can_bid_be_posted(70, 1, 70, market, replace_existing=True) is True
    assert base.can_bid_be_posted(70.001, 1, 70, market, replace_existing=True) is False


@pytest.mark.parametrize("market_class", [TwoSidedMarket])
@patch(
    "gsy_framework.constants_limits.ConstSettings.MASettings.MARKET_TYPE",
    SpotMarketTypeEnum.TWO_SIDED.value,
)
def test_post_bid_with_replace_existing(market_class, base):
    """Calling post_bid with replace_existing=True triggers the removal of the existing bids."""

    market = market_class(time_slot=pendulum.now())
    base.area._market = market

    _ = base.post_bid(market, 10, 5, replace_existing=False)
    _ = base.post_bid(market, 12, 6, replace_existing=False)
    bid_3 = base.post_bid(market, 8, 4, replace_existing=True)
    bid_4 = base.post_bid(market, 4, 2, replace_existing=False)

    assert base.get_posted_bids(market) == [bid_3, bid_4]


@pytest.mark.parametrize("market_class", [TwoSidedMarket])
@patch(
    "gsy_framework.constants_limits.ConstSettings.MASettings.MARKET_TYPE",
    SpotMarketTypeEnum.TWO_SIDED.value,
)
def test_post_bid_without_replace_existing(market_class, base):
    """Calling post_bid with replace_existing=False does not trigger the removal of the existing
    bids.
    """
    market = market_class(time_slot=pendulum.now())
    base.area._market = market

    bid_1 = base.post_bid(market, 10, 5, replace_existing=False)
    bid_2 = base.post_bid(market, 12, 6, replace_existing=False)
    bid_3 = base.post_bid(market, 8, 4, replace_existing=False)

    assert base.get_posted_bids(market) == [bid_1, bid_2, bid_3]


@pytest.mark.parametrize("market_class", [OneSidedMarket, TwoSidedMarket])
def test_post_offer_creates_offer_with_correct_parameters(market_class):
    """Calling post_offer with replace_existing=False does not trigger the removal of the existing
    offers.
    """
    strategy = BaseStrategy()
    strategy.owner = FakeOwner()
    strategy.area = FakeArea()

    market = market_class(bc=NonBlockchainInterface(str(uuid4())), time_slot=pendulum.now())
    strategy.area._market = market

    offer_args = {"price": 1, "energy": 1}

    offer = strategy.post_offer(market, replace_existing=False, **offer_args)

    # The offer is created with the expected parameters
    assert offer.price == 1
    assert offer.energy == 1
    assert offer.seller.name == strategy.owner.name


@pytest.mark.parametrize("market_class", [OneSidedMarket, TwoSidedMarket])
def test_post_offer_with_replace_existing(market_class):
    """Calling post_offer with replace_existing triggers the removal of the existing offers."""

    strategy = BaseStrategy()
    strategy.owner = FakeOwner()
    strategy.area = FakeArea()

    market = market_class(bc=NonBlockchainInterface(str(uuid4())), time_slot=pendulum.now())
    strategy.area._market = market

    # Post a first offer on the market
    offer_1_args = {
        "price": 1,
        "energy": 1,
        "seller": TraderDetails("FakeOwner", "", "FakeOwnerOrigin", ""),
    }
    offer = strategy.post_offer(market, replace_existing=False, **offer_1_args)
    assert strategy.offers.open_in_market(market.id) == [offer]

    # Post a new offer not replacing the previous ones
    offer_2_args = {
        "price": 1,
        "energy": 1,
        "seller": TraderDetails("FakeOwner", "", "FakeOwnerOrigin", ""),
    }
    offer_2 = strategy.post_offer(market, replace_existing=False, **offer_2_args)
    assert strategy.offers.open_in_market(market.id) == [offer, offer_2]

    # Post a new offer replacing the previous ones (default behavior)
    offer_3_args = {
        "price": 1,
        "energy": 1,
        "seller": TraderDetails("FakeOwner", "", "FakeOwnerOrigin", ""),
    }
    offer_3 = strategy.post_offer(market, **offer_3_args)
    assert strategy.offers.open_in_market(market.id) == [offer_3]


def test_energy_traded_and_cost_traded(base):
    ConstSettings.MASettings.MARKET_TYPE = 2
    market = FakeMarket(raises=True)
    base.area._market = market
    o1 = Offer("id", pendulum.now(), price=1, energy=23, seller=TraderDetails("A", ""))
    o2 = Offer("id2", pendulum.now(), price=1, energy=27, seller=TraderDetails("A", ""))
    o3 = Offer("id3", pendulum.now(), price=1, energy=10, seller=TraderDetails("A", ""))
    base.offers.sold_offer(o1, market.id)
    base.offers.sold_offer(o2, market.id)
    base.offers.sold_offer(o3, market.id)
    assert base.energy_traded(market.id) == 60
    assert base.energy_traded_costs(market.id) == 3
    b1 = base.post_bid(market, 1, 23)
    b2 = base.post_bid(market, 1, 27)
    b3 = base.post_bid(market, 1, 10)
    base.add_bid_to_bought(b1, market.id)
    base.add_bid_to_bought(b2, market.id)
    base.add_bid_to_bought(b3, market.id)
    # energy and costs get accumulated from both offers and bids
    assert base.energy_traded(market.id) == 120
    assert base.energy_traded_costs(market.id) == 6


def test_get_market_from_id_returns_none_value_for_nonexistent_market(base):
    base.area.settlement_markets = {}
    market = base.get_market_from_id("123123123")
    assert market is None
