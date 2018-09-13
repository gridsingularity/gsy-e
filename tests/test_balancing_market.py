import pytest
from pendulum import DateTime

from d3a.models.events import MarketEvent

from d3a.exceptions import MarketReadOnlyException, OfferNotFoundException, \
    InvalidTrade, DeviceNotInRegistryError
from d3a.models.market import BalancingMarket

from d3a.device_registry import DeviceRegistry
DeviceRegistry.REGISTRY = {
    "A": {"balancing rates": (23, 25)},
    "someone": {"balancing rates": (23, 25)},
    "seller": {"balancing rates": (23, 25)},
}


@pytest.yield_fixture
def market():
    return BalancingMarket()


def test_device_registry(market: BalancingMarket):
    with pytest.raises(DeviceNotInRegistryError):
        market.balancing_offer(10, 10, 'noone')


def test_market_offer(market: BalancingMarket):
    offer = market.balancing_offer(10, 20, 'someone')

    assert market.offers[offer.id] == offer
    assert offer.energy == 20
    assert offer.price == 10
    assert offer.seller == 'someone'
    assert len(offer.id) == 36


def test_market_offer_readonly(market: BalancingMarket):
    market.readonly = True
    with pytest.raises(MarketReadOnlyException):
        market.balancing_offer(10, 10, 'A')


def test_market_offer_delete(market: BalancingMarket):
    offer = market.balancing_offer(20, 10, 'someone')
    market.delete_offer(offer)

    assert offer.id not in market.offers


def test_market_offer_delete_id(market: BalancingMarket):
    offer = market.balancing_offer(20, 10, 'someone')
    market.delete_offer(offer.id)

    assert offer.id not in market.offers


def test_market_offer_delete_missing(market: BalancingMarket):
    with pytest.raises(OfferNotFoundException):
        market.delete_offer("no such offer")


def test_market_offer_delete_readonly(market: BalancingMarket):
    market.readonly = True
    with pytest.raises(MarketReadOnlyException):
        market.delete_offer("no such offer")


def test_balancing_market_trade(market: BalancingMarket):
    offer = market.balancing_offer(20, 10, 'A')

    now = DateTime.now()
    trade = market.accept_balancing_offer(offer, 'B', time=now, energy=10)
    assert trade
    assert trade == market.trades[0]
    assert trade.id
    assert trade.time == now
    assert trade.offer is offer
    assert trade.seller == 'A'
    assert trade.buyer == 'B'


def test_balancing_market_negative_offer_trade(market: BalancingMarket):
    offer = market.balancing_offer(20, -10, 'A')

    now = DateTime.now()
    trade = market.accept_balancing_offer(offer, 'B', time=now, energy=-10)
    assert trade
    assert trade == market.trades[0]
    assert trade.id
    assert trade.time == now
    assert trade.offer is offer
    assert trade.seller == 'A'
    assert trade.buyer == 'B'


def test_market_trade_readonly(market: BalancingMarket):
    offer = market.balancing_offer(20, 10, 'A')
    market.readonly = True
    with pytest.raises(MarketReadOnlyException):
        market.accept_balancing_offer(offer, 'B')


def test_market_trade_not_found(market: BalancingMarket):
    offer = market.balancing_offer(20, 10, 'A')

    assert market.accept_balancing_offer(offer, 'B', energy=10)
    with pytest.raises(OfferNotFoundException):
        market.accept_balancing_offer(offer, 'B', energy=10)


def test_market_trade_partial(market: BalancingMarket):
    offer = market.balancing_offer(20, 20, 'A')

    trade = market.accept_balancing_offer(offer, 'B', energy=5)
    assert trade
    assert trade == market.trades[0]
    assert trade.id
    assert trade.offer is not offer
    assert trade.offer.energy == 5
    assert trade.offer.price == 5
    assert trade.offer.seller == 'A'
    assert trade.seller == 'A'
    assert trade.buyer == 'B'
    assert len(market.offers) == 1
    new_offer = list(market.offers.values())[0]
    assert new_offer is not offer
    assert new_offer.energy == 15
    assert new_offer.price == 15
    assert new_offer.seller == 'A'
    assert new_offer.id != offer.id


@pytest.mark.parametrize('energy', (0, 21))
def test_market_trade_partial_invalid(market: BalancingMarket, energy):
    offer = market.balancing_offer(20, 20, 'A')

    with pytest.raises(InvalidTrade):
        market.accept_balancing_offer(offer, 'B', energy=energy)


def test_market_avg_offer_price(market: BalancingMarket):
    market.balancing_offer(1, 1, 'A')
    market.balancing_offer(3, 1, 'A')

    assert market.avg_offer_price == 2


def test_market_avg_offer_price_empty(market: BalancingMarket):
    assert market.avg_offer_price == 0


def test_market_sorted_offers(market: BalancingMarket):
    market.balancing_offer(5, 1, 'A')
    market.balancing_offer(3, 1, 'A')
    market.balancing_offer(1, 1, 'A')
    market.balancing_offer(2, 1, 'A')
    market.balancing_offer(4, 1, 'A')

    assert [o.price for o in market.sorted_offers] == [1, 2, 3, 4, 5]


def test_market_most_affordable_offers(market: BalancingMarket):
    market.balancing_offer(5, 1, 'A')
    market.balancing_offer(3, 1, 'A')
    market.balancing_offer(1, 1, 'A')
    market.balancing_offer(10, 10, 'A')
    market.balancing_offer(20, 20, 'A')
    market.balancing_offer(20000, 20000, 'A')
    market.balancing_offer(2, 1, 'A')
    market.balancing_offer(4, 1, 'A')

    assert {o.price for o in market.most_affordable_offers} == {1, 10, 20, 20000}


def test_market_listeners_init(called):
    market = BalancingMarket(notification_listener=called)
    market.balancing_offer(10, 20, 'A')
    assert len(called.calls) == 1


def test_market_listeners_add(market, called):
    market.add_listener(called)
    market.balancing_offer(10, 20, 'A')
    assert len(called.calls) == 1


def test_market_listeners_offer(market, called):
    market.add_listener(called)
    offer = market.balancing_offer(10, 20, 'A')

    assert len(called.calls) == 1
    assert called.calls[0][0] == (repr(MarketEvent.BALANCING_OFFER), )
    assert called.calls[0][1] == {'offer': repr(offer), 'market': repr(market)}


def test_market_listeners_offer_changed(market, called):
    market.add_listener(called)
    offer = market.balancing_offer(10, 20, 'A')
    market.accept_balancing_offer(offer, 'B', energy=3)

    assert len(called.calls) == 3
    assert called.calls[1][0] == (repr(MarketEvent.BALANCING_OFFER_CHANGED), )
    call_kwargs = called.calls[1][1]
    call_kwargs.pop('market', None)
    assert call_kwargs == {
        'existing_offer': repr(offer),
        'new_offer': repr(list(market.offers.values())[0])
    }


def test_market_listeners_offer_deleted(market, called):
    market.add_listener(called)
    offer = market.balancing_offer(10, 20, 'A')
    market.delete_offer(offer)

    assert len(called.calls) == 2
    assert called.calls[1][0] == (repr(MarketEvent.OFFER_DELETED), )
    assert called.calls[1][1] == {'offer': repr(offer), 'market': repr(market)}


def test_market_accept_offer_yields_partial_trade(market: BalancingMarket):
    offer = market.balancing_offer(2.0, 4, 'seller')
    trade = market.accept_balancing_offer(offer, 'buyer', energy=1)
    assert trade.offer.id == offer.id and trade.offer.energy == 1 and trade.residual.energy == 3
