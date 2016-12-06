from uuid import uuid4

from d3a.models.events import OfferEvent
from d3a.models.market import Offer


def test_offer_id_stringified():
    offer = Offer(object(), 10, 20, 'A')

    assert isinstance(offer.id, str)
    assert "<object object at" in offer.id


def test_offer_listener_deleted(called):
    offer = Offer(str(uuid4()), 10, 20, 'A')
    offer.add_listener(OfferEvent.DELETED, called)
    offer_repr = repr(offer)

    del offer

    assert len(called.calls) == 1
    assert called.calls[0][0] == ()
    assert called.calls[0][1] == {'offer': offer_repr}


def test_offer_listener_accepted(called):
    offer = Offer(str(uuid4()), 10, 10, 'A')
    offer.add_listener(OfferEvent.ACCEPTED, called)

    trade = object()
    market = object()
    offer._traded(trade, market)

    assert len(called.calls) == 1
    assert called.calls[0][0] == ()
    assert called.calls[0][1] == {
        'market': repr(market),
        'trade': repr(trade),
        'offer': repr(offer)
    }


def test_offer_listener_multiple(called):
    offer = Offer(str(uuid4()), 10, 10, 'A')
    offer.add_listener((OfferEvent.ACCEPTED, OfferEvent.DELETED), called)
    offer_repr = repr(offer)

    trade = object()
    market = object()
    offer._traded(trade, market)

    del offer

    assert len(called.calls) == 2
    assert called.calls[0][0] == ()
    assert called.calls[0][1] == {
        'market': repr(market),
        'trade': repr(trade),
        'offer': offer_repr
    }
    assert called.calls[1][0] == ()
    assert called.calls[1][1] == {'offer': offer_repr}
