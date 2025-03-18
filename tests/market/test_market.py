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

import string
from copy import deepcopy
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from deepdiff import DeepDiff
from gsy_framework.constants_limits import ConstSettings, TIME_ZONE
from gsy_framework.data_classes import Bid, Offer, TraderDetails
from gsy_framework.utils import datetime_to_string_incl_seconds
from hypothesis import strategies as st
from hypothesis.control import assume
from hypothesis.stateful import Bundle, RuleBasedStateMachine, precondition, rule
from pendulum import now

from gsy_e.events.event_structures import MarketEvent
from gsy_e.gsy_e_core.blockchain_interface import NonBlockchainInterface
from gsy_e.gsy_e_core.device_registry import DeviceRegistry
from gsy_e.gsy_e_core.exceptions import (
    DeviceNotInRegistryError,
    InvalidBalancingTradeException,
    NegativeEnergyOrderException,
    InvalidTrade,
    MarketReadOnlyException,
    OfferNotFoundException,
)
from gsy_e.gsy_e_core.util import add_or_create_key, subtract_or_create_key
from gsy_e.models.market.balancing import BalancingMarket
from gsy_e.models.market.one_sided import OneSidedMarket
from gsy_e.models.market.settlement import SettlementMarket
from gsy_e.models.market.two_sided import TwoSidedMarket

device_registry_dict = {
    "A": {"balancing rates": (33, 35)},
    "S": {"balancing rates": (33, 35)},
    "someone": {"balancing rates": (33, 35)},
    "seller": {"balancing rates": (33, 35)},
}

seller_details = TraderDetails("S", "", "S", "")
buyer_details = TraderDetails("B", "", "B", "")


@pytest.fixture(scope="function", autouse=True)
def device_registry_auto_fixture():
    """Fixture for device registry."""
    DeviceRegistry.REGISTRY = device_registry_dict
    ConstSettings.MASettings.MARKET_TYPE = 1
    yield
    DeviceRegistry.REGISTRY = {}


@pytest.fixture(name="market")
def market_fixture():
    """Fixture for two sided market."""
    return TwoSidedMarket(time_slot=now())


def test_device_registry(market=BalancingMarket()):
    with pytest.raises(DeviceNotInRegistryError):
        market.balancing_offer(10, 10, TraderDetails("noone", ""))


@pytest.mark.parametrize(
    "market, offer",
    [
        (OneSidedMarket(bc=NonBlockchainInterface(str(uuid4())), time_slot=now()), "offer"),
        (
            BalancingMarket(bc=NonBlockchainInterface(str(uuid4())), time_slot=now()),
            "balancing_offer",
        ),
        (SettlementMarket(bc=NonBlockchainInterface(str(uuid4())), time_slot=now()), "offer"),
    ],
)
def test_market_offer(market, offer):
    ConstSettings.BalancingSettings.ENABLE_BALANCING_MARKET = True
    e_offer = getattr(market, offer)(10, 20, TraderDetails("someone", "", "someone", ""))
    assert market.offers[e_offer.id] == e_offer
    assert e_offer.energy == 20
    assert e_offer.price == 10
    assert e_offer.seller.name == "someone"
    assert len(e_offer.id) == 36
    assert e_offer.creation_time == market.now
    assert e_offer.time_slot == market.time_slot


@pytest.mark.parametrize(
    "market",
    [
        TwoSidedMarket(bc=NonBlockchainInterface(str(uuid4())), time_slot=now()),
        SettlementMarket(bc=NonBlockchainInterface(str(uuid4())), time_slot=now()),
    ],
)
def test_market_bid(market):
    ConstSettings.BalancingSettings.ENABLE_BALANCING_MARKET = True
    bid = market.bid(10, 20, buyer_details)
    assert market.bids[bid.id] == bid
    assert bid.energy == 20
    assert bid.price == 10
    assert bid.buyer.name == buyer_details.name
    assert len(bid.id) == 36
    assert bid.creation_time == market.now
    assert bid.time_slot == market.time_slot


def test_market_offer_invalid(market: OneSidedMarket):
    with pytest.raises(NegativeEnergyOrderException):
        market.offer(10, -1, buyer_details)


@pytest.mark.parametrize(
    "market, offer",
    [
        (TwoSidedMarket(), "offer"),
        (BalancingMarket(), "balancing_offer"),
        (SettlementMarket(), "offer"),
    ],
)
def test_market_offer_readonly(market, offer):
    market.readonly = True
    with pytest.raises(MarketReadOnlyException):
        getattr(market, offer)(10, 10, seller_details)


@pytest.mark.parametrize(
    "market",
    [
        OneSidedMarket(bc=MagicMock()),
        BalancingMarket(bc=MagicMock()),
        SettlementMarket(bc=MagicMock()),
    ],
)
def test_market_offer_delete_missing(market):
    with pytest.raises(OfferNotFoundException):
        market.delete_offer("no such offer")


@pytest.mark.parametrize(
    "market",
    [
        OneSidedMarket(bc=MagicMock()),
        BalancingMarket(bc=MagicMock()),
        SettlementMarket(bc=MagicMock()),
    ],
)
def test_market_offer_delete_readonly(market):
    market.readonly = True
    with pytest.raises(MarketReadOnlyException):
        market.delete_offer("no such offer")


@pytest.mark.parametrize(
    "market, offer, accept_offer",
    [
        (
            OneSidedMarket(bc=NonBlockchainInterface(str(uuid4())), time_slot=now(tz=TIME_ZONE)),
            "offer",
            "accept_offer",
        ),
        (
            BalancingMarket(bc=NonBlockchainInterface(str(uuid4())), time_slot=now(tz=TIME_ZONE)),
            "balancing_offer",
            "accept_offer",
        ),
        (
            SettlementMarket(bc=NonBlockchainInterface(str(uuid4())), time_slot=now(tz=TIME_ZONE)),
            "offer",
            "accept_offer",
        ),
    ],
)
def test_market_trade(market, offer, accept_offer):
    e_offer = getattr(market, offer)(20, 10, seller_details)
    trade = getattr(market, accept_offer)(offer_or_id=e_offer, buyer=buyer_details, energy=10)
    assert trade
    assert trade == market.trades[0]
    assert trade.id
    assert trade.creation_time == market.now
    assert trade.time_slot == market.time_slot
    assert trade.match_details["offer"] == e_offer
    assert trade.seller.name == seller_details.name
    assert trade.buyer.name == buyer_details.name


def test_orders_per_slot(market):
    """Test whether the orders_per_slot method returns order in format format."""
    creation_time = now()
    market.bids = {"bid1": Bid("bid1", creation_time, 10, 10, TraderDetails("buyer", ""))}
    market.offers = {"offer1": Offer("offer1", creation_time, 10, 10, TraderDetails("seller", ""))}
    order_dict_diff = DeepDiff(
        market.orders_per_slot(),
        {
            market.time_slot_str: {
                "bids": [
                    {
                        "buyer": {
                            "name": "buyer",
                            "uuid": "",
                            "origin": None,
                            "origin_uuid": None,
                        },
                        "energy": 10,
                        "price": 10,
                        "energy_rate": 1.0,
                        "id": "bid1",
                        "original_price": 10,
                        "time_slot": "",
                        "creation_time": datetime_to_string_incl_seconds(creation_time),
                        "type": "Bid",
                    }
                ],
                "offers": [
                    {
                        "energy": 10,
                        "price": 10,
                        "energy_rate": 1.0,
                        "id": "offer1",
                        "original_price": 10,
                        "seller": {
                            "name": "seller",
                            "uuid": "",
                            "origin": None,
                            "origin_uuid": None,
                        },
                        "time_slot": "",
                        "creation_time": datetime_to_string_incl_seconds(creation_time),
                        "type": "Offer",
                    }
                ],
            }
        },
    )
    assert len(order_dict_diff) == 0


def test_balancing_market_negative_offer_trade(
    market=BalancingMarket(bc=NonBlockchainInterface(str(uuid4()))),
):  # NOQA
    offer = market.balancing_offer(20, -10, seller_details)
    trade = market.accept_offer(offer, buyer_details, energy=-10)
    assert trade
    assert trade == market.trades[0]
    assert trade.id
    assert trade.creation_time == market.now
    assert trade.time_slot == market.time_slot
    assert trade.match_details["offer"] is offer
    assert trade.seller.name == seller_details.name
    assert trade.buyer.name == buyer_details.name


@pytest.mark.parametrize(
    "market, offer, accept_offer",
    [
        (
            OneSidedMarket(bc=NonBlockchainInterface(str(uuid4())), time_slot=now()),
            "offer",
            "accept_offer",
        ),
        (
            BalancingMarket(bc=NonBlockchainInterface(str(uuid4())), time_slot=now()),
            "balancing_offer",
            "accept_offer",
        ),
        (
            SettlementMarket(bc=NonBlockchainInterface(str(uuid4())), time_slot=now()),
            "offer",
            "accept_offer",
        ),
    ],
)
def test_market_trade_by_id(market, offer, accept_offer):
    e_offer = getattr(market, offer)(20, 10, seller_details)
    trade = getattr(market, accept_offer)(offer_or_id=e_offer.id, buyer=buyer_details, energy=10)
    assert trade


@pytest.mark.parametrize(
    "market, offer, accept_offer",
    [
        (OneSidedMarket(bc=MagicMock(), time_slot=now()), "offer", "accept_offer"),
        (BalancingMarket(bc=MagicMock(), time_slot=now()), "balancing_offer", "accept_offer"),
        (SettlementMarket(bc=MagicMock(), time_slot=now()), "offer", "accept_offer"),
    ],
)
def test_market_trade_readonly(market, offer, accept_offer):
    e_offer = getattr(market, offer)(20, 10, seller_details)
    market.readonly = True
    with pytest.raises(MarketReadOnlyException):
        getattr(market, accept_offer)(e_offer, buyer_details)


@pytest.mark.parametrize(
    "market, offer, accept_offer",
    [
        (
            OneSidedMarket(bc=NonBlockchainInterface(str(uuid4())), time_slot=now()),
            "offer",
            "accept_offer",
        ),
        (
            BalancingMarket(bc=NonBlockchainInterface(str(uuid4())), time_slot=now()),
            "balancing_offer",
            "accept_offer",
        ),
        (
            SettlementMarket(bc=NonBlockchainInterface(str(uuid4())), time_slot=now()),
            "offer",
            "accept_offer",
        ),
    ],
)
def test_market_trade_not_found(market, offer, accept_offer):
    e_offer = getattr(market, offer)(20, 10, seller_details)

    assert getattr(market, accept_offer)(offer_or_id=e_offer, buyer=buyer_details, energy=10)
    with pytest.raises(OfferNotFoundException):
        getattr(market, accept_offer)(offer_or_id=e_offer, buyer=buyer_details, energy=10)


@pytest.mark.parametrize(
    "market, offer, accept_offer",
    [
        (
            OneSidedMarket(bc=NonBlockchainInterface(str(uuid4())), time_slot=now()),
            "offer",
            "accept_offer",
        ),
        (
            BalancingMarket(bc=NonBlockchainInterface(str(uuid4())), time_slot=now()),
            "balancing_offer",
            "accept_offer",
        ),
        (
            SettlementMarket(bc=NonBlockchainInterface(str(uuid4())), time_slot=now()),
            "offer",
            "accept_offer",
        ),
    ],
)
def test_market_trade_partial(market, offer, accept_offer):
    e_offer = getattr(market, offer)(20, 20, seller_details)

    trade = getattr(market, accept_offer)(offer_or_id=e_offer, buyer=buyer_details, energy=5)
    assert trade
    assert trade == market.trades[0]
    assert trade.id
    assert trade.match_details["offer"] is not e_offer
    assert trade.traded_energy == 5
    assert trade.trade_price == 5
    assert trade.match_details["offer"].seller.name == seller_details.name
    assert trade.seller.name == seller_details.name
    assert trade.buyer.name == buyer_details.name
    assert len(market.offers) == 1
    new_offer = list(market.offers.values())[0]
    assert new_offer is not e_offer
    assert new_offer.energy == 15
    assert new_offer.price == 15
    assert new_offer.seller.name == seller_details.name
    assert new_offer.id != e_offer.id


@pytest.mark.parametrize(
    "market, offer, accept_offer, energy, exception",
    [
        (
            OneSidedMarket(bc=MagicMock(), time_slot=now()),
            "offer",
            "accept_offer",
            0,
            InvalidTrade,
        ),
        (
            OneSidedMarket(bc=MagicMock(), time_slot=now()),
            "offer",
            "accept_offer",
            21,
            InvalidTrade,
        ),
        (
            BalancingMarket(bc=MagicMock(), time_slot=now()),
            "balancing_offer",
            "accept_offer",
            0,
            InvalidBalancingTradeException,
        ),
        (
            BalancingMarket(bc=MagicMock(), time_slot=now()),
            "balancing_offer",
            "accept_offer",
            21,
            InvalidBalancingTradeException,
        ),
        (
            SettlementMarket(bc=MagicMock(), time_slot=now()),
            "offer",
            "accept_offer",
            0,
            InvalidTrade,
        ),
        (
            SettlementMarket(bc=MagicMock(), time_slot=now()),
            "offer",
            "accept_offer",
            21,
            InvalidTrade,
        ),
    ],
)
def test_market_trade_partial_invalid(market, offer, accept_offer, energy, exception):
    e_offer = getattr(market, offer)(20, 20, seller_details)
    with pytest.raises(exception):
        getattr(market, accept_offer)(offer_or_id=e_offer, buyer=buyer_details.name, energy=energy)


def test_market_acct_simple(
    market=OneSidedMarket(bc=NonBlockchainInterface(str(uuid4())), time_slot=now())
):
    offer = market.offer(20, 10, TraderDetails("A", "", "A", ""))
    market.accept_offer(offer, TraderDetails("B", "", "B", ""))

    assert market.traded_energy["A"] == offer.energy
    assert market.traded_energy["B"] == -offer.energy
    assert market.bought_energy("A") == 0
    assert market.bought_energy("B") == offer.energy
    assert market.sold_energy("A") == offer.energy
    assert market.sold_energy("B") == 0


def test_market_acct_multiple(
    market=OneSidedMarket(bc=NonBlockchainInterface(str(uuid4())), time_slot=now())
):
    offer1 = market.offer(10, 20, TraderDetails("A", "", "A", ""))
    offer2 = market.offer(10, 10, TraderDetails("A", "", "A", ""))
    market.accept_offer(offer1, TraderDetails("B", "", "B", ""))
    market.accept_offer(offer2, TraderDetails("C", "", "C", ""))

    assert market.traded_energy["A"] == offer1.energy + offer2.energy == 30
    assert market.traded_energy["B"] == -offer1.energy == -20
    assert market.traded_energy["C"] == -offer2.energy == -10
    assert market.bought_energy("A") == 0
    assert market.sold_energy("A") == offer1.energy + offer2.energy == 30
    assert market.bought_energy("B") == offer1.energy == 20
    assert market.bought_energy("C") == offer2.energy == 10


@pytest.mark.parametrize(
    "market, offer",
    [
        (OneSidedMarket(bc=NonBlockchainInterface(str(uuid4())), time_slot=now()), "offer"),
        (
            BalancingMarket(bc=NonBlockchainInterface(str(uuid4())), time_slot=now()),
            "balancing_offer",
        ),
        (SettlementMarket(bc=NonBlockchainInterface(str(uuid4())), time_slot=now()), "offer"),
    ],
)
def test_market_sorted_offers(market, offer):
    getattr(market, offer)(5, 1, seller_details)
    getattr(market, offer)(3, 1, seller_details)
    getattr(market, offer)(1, 1, seller_details)
    getattr(market, offer)(2, 1, seller_details)
    getattr(market, offer)(4, 1, seller_details)

    assert [o.price for o in market.sorted_offers] == [1, 2, 3, 4, 5]


@pytest.mark.parametrize(
    "market, offer",
    [
        (OneSidedMarket(bc=NonBlockchainInterface(str(uuid4())), time_slot=now()), "offer"),
        (
            BalancingMarket(bc=NonBlockchainInterface(str(uuid4())), time_slot=now()),
            "balancing_offer",
        ),
        (SettlementMarket(bc=NonBlockchainInterface(str(uuid4())), time_slot=now()), "offer"),
    ],
)
def test_market_most_affordable_offers(market, offer):
    getattr(market, offer)(5, 1, seller_details)
    getattr(market, offer)(3, 1, seller_details)
    getattr(market, offer)(1, 1, seller_details)
    getattr(market, offer)(10, 10, seller_details)
    getattr(market, offer)(20, 20, seller_details)
    getattr(market, offer)(20000, 20000, seller_details)
    getattr(market, offer)(2, 1, seller_details)
    getattr(market, offer)(4, 1, seller_details)

    assert {o.price for o in market.most_affordable_offers} == {1, 10, 20, 20000}


@pytest.mark.parametrize(
    "market, offer",
    [(OneSidedMarket, "offer"), (BalancingMarket, "balancing_offer"), (SettlementMarket, "offer")],
)
def test_market_listeners_init(market, offer, called):
    markt = market(bc=MagicMock(), time_slot=now(), notification_listener=called)
    getattr(markt, offer)(10, 20, seller_details)
    assert len(called.calls) == 1


@pytest.mark.parametrize(
    "market, offer, add_listener",
    [
        (OneSidedMarket(bc=MagicMock(), time_slot=now()), "offer", "add_listener"),
        (BalancingMarket(bc=MagicMock(), time_slot=now()), "balancing_offer", "add_listener"),
        (SettlementMarket(bc=MagicMock(), time_slot=now()), "offer", "add_listener"),
    ],
)
def test_market_listeners_add(market, offer, add_listener, called):
    getattr(market, add_listener)(called)
    getattr(market, offer)(10, 20, seller_details)

    assert len(called.calls) == 1


@pytest.mark.parametrize(
    "market, offer, add_listener, event",
    [
        (
            OneSidedMarket(bc=MagicMock(), time_slot=now()),
            "offer",
            "add_listener",
            MarketEvent.OFFER,
        ),
        (
            BalancingMarket(bc=MagicMock(), time_slot=now()),
            "balancing_offer",
            "add_listener",
            MarketEvent.BALANCING_OFFER,
        ),
        (
            SettlementMarket(bc=MagicMock(), time_slot=now()),
            "offer",
            "add_listener",
            MarketEvent.OFFER,
        ),
    ],
)
def test_market_listeners_offer(market, offer, add_listener, event, called):
    getattr(market, add_listener)(called)
    e_offer = getattr(market, offer)(10, 20, seller_details)
    assert len(called.calls) == 1
    assert called.calls[0][0] == (repr(event),)
    assert called.calls[0][1] == {"offer": repr(e_offer), "market_id": repr(market.id)}


@pytest.mark.parametrize(
    "market, offer, accept_offer, add_listener, event",
    [
        (
            OneSidedMarket(bc=NonBlockchainInterface(str(uuid4())), time_slot=now()),
            "offer",
            "accept_offer",
            "add_listener",
            MarketEvent.OFFER_SPLIT,
        ),
        (
            BalancingMarket(bc=NonBlockchainInterface(str(uuid4())), time_slot=now()),
            "balancing_offer",
            "accept_offer",
            "add_listener",
            MarketEvent.BALANCING_OFFER_SPLIT,
        ),
        (
            SettlementMarket(bc=NonBlockchainInterface(str(uuid4())), time_slot=now()),
            "offer",
            "accept_offer",
            "add_listener",
            MarketEvent.OFFER_SPLIT,
        ),
    ],
)
def test_market_listeners_offer_split(market, offer, accept_offer, add_listener, event, called):
    # pylint: disable=too-many-arguments
    getattr(market, add_listener)(called)
    e_offer = getattr(market, offer)(10.0, 20, seller_details)
    getattr(market, accept_offer)(e_offer, buyer_details, energy=3.0)
    assert len(called.calls) == 3
    assert called.calls[1][0] == (repr(event),)
    call_kwargs = called.calls[1][1]
    call_kwargs.pop("market_id", None)
    a_offer = deepcopy(e_offer)
    a_offer.price = e_offer.price / 20 * 3
    a_offer.energy = e_offer.energy / 20 * 3
    assert call_kwargs == {
        "original_offer": repr(e_offer),
        "accepted_offer": repr(a_offer),
        "residual_offer": repr(list(market.offers.values())[0]),
    }


@pytest.mark.parametrize(
    "market, offer, delete_offer, add_listener, event",
    [
        (
            OneSidedMarket(bc=MagicMock(), time_slot=now()),
            "offer",
            "delete_offer",
            "add_listener",
            MarketEvent.OFFER_DELETED,
        ),
        (
            BalancingMarket(bc=MagicMock(), time_slot=now()),
            "balancing_offer",
            "delete_balancing_offer",
            "add_listener",
            MarketEvent.BALANCING_OFFER_DELETED,
        ),
        (
            SettlementMarket(bc=MagicMock(), time_slot=now()),
            "offer",
            "delete_offer",
            "add_listener",
            MarketEvent.OFFER_DELETED,
        ),
    ],
)
def test_market_listeners_offer_deleted(market, offer, delete_offer, add_listener, event, called):
    # pylint: disable=too-many-arguments
    getattr(market, add_listener)(called)
    e_offer = getattr(market, offer)(10, 20, seller_details)
    getattr(market, delete_offer)(e_offer)

    assert len(called.calls) == 2
    assert called.calls[1][0] == (repr(event),)
    assert called.calls[1][1] == {"offer": repr(e_offer), "market_id": repr(market.id)}


@pytest.mark.parametrize(("last_offer_size", "traded_energy"), ((20, 10), (30, 0), (40, -10)))
def test_market_issuance_acct_reverse(last_offer_size, traded_energy):
    market = OneSidedMarket(bc=NonBlockchainInterface(str(uuid4())), time_slot=now())
    offer1 = market.offer(10, 20, TraderDetails("A", "", "A", ""))
    offer2 = market.offer(10, 10, TraderDetails("A", "", "A", ""))
    offer3 = market.offer(10, last_offer_size, TraderDetails("D", "", "D", ""))

    market.accept_offer(offer1, TraderDetails("B", "", "B", ""))
    market.accept_offer(offer2, TraderDetails("C", ""))
    market.accept_offer(offer3, TraderDetails("A", "", "A", ""))
    assert market.traded_energy["A"] == traded_energy


@pytest.mark.parametrize(
    "market, offer, accept_offer",
    [
        (
            OneSidedMarket(bc=NonBlockchainInterface(str(uuid4())), time_slot=now()),
            "offer",
            "accept_offer",
        ),
        (
            BalancingMarket(bc=NonBlockchainInterface(str(uuid4())), time_slot=now()),
            "balancing_offer",
            "accept_offer",
        ),
        (
            SettlementMarket(bc=NonBlockchainInterface(str(uuid4())), time_slot=now()),
            "offer",
            "accept_offer",
        ),
    ],
)
def test_market_accept_offer_yields_partial_trade(market, offer, accept_offer):
    """Test market accept offer returns partial trade."""
    e_offer = getattr(market, offer)(2.0, 4, seller_details)
    trade = getattr(market, accept_offer)(e_offer, buyer_details, energy=1)
    assert (
        trade.match_details["offer"].id == e_offer.id
        and trade.traded_energy == 1
        and trade.residual.energy == 3
    )


class MarketStateMachine(RuleBasedStateMachine):
    """State machine for Market"""

    # pylint: disable=missing-function-docstring
    offers = Bundle("Offers")
    actors = Bundle("Actors")

    def __init__(self):
        self.market = OneSidedMarket(bc=NonBlockchainInterface(str(uuid4())), time_slot=now())
        super().__init__()

    @rule(
        target=actors,
        actor=st.text(min_size=1, max_size=3, alphabet=string.ascii_letters + string.digits),
    )
    def new_actor(self, actor):
        # pylint: disable=no-self-use
        return actor

    @rule(
        target=offers,
        seller=actors,
        energy=st.integers(min_value=1),
        price=st.integers(min_value=0),
    )
    def offer(self, seller, energy, price):
        return self.market.offer(price, energy, TraderDetails(seller, ""))

    @rule(offer=offers, buyer=actors)
    def trade(self, offer, buyer):
        assume(offer.id in self.market.offers)
        self.market.accept_offer(offer, TraderDetails(buyer, ""))

    @precondition(lambda self: self.market.trades)
    @rule()
    def check_avg_trade_price(self):
        price = sum(t.trade_price for t in self.market.trades)
        energy = sum(t.traded_energy for t in self.market.trades)
        assert self.market.avg_trade_price == round(price / energy, 4)

    @precondition(lambda self: self.market.traded_energy)
    @rule()
    def check_acct(self):
        actor_sums = {}
        for t in self.market.trades:
            actor_sums = add_or_create_key(actor_sums, t.seller.name, t.traded_energy)
            actor_sums = subtract_or_create_key(actor_sums, t.buyer.name, t.traded_energy)
        for actor, sum_ in actor_sums.items():
            assert self.market.traded_energy[actor] == sum_
        assert sum(self.market.traded_energy.values()) == 0


TestMarketIOU = MarketStateMachine.TestCase
