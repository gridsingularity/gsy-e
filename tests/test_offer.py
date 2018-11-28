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

from uuid import uuid4

from d3a.events.event_structures import OfferEvent
from d3a.models.market.market_structures import Offer, BalancingOffer


@pytest.mark.parametrize("offer", [Offer, BalancingOffer])
def test_offer_id_stringified(offer):
    offer = offer(object(), 10, 20, 'A')

    assert isinstance(offer.id, str)
    assert "<object object at" in offer.id


@pytest.mark.parametrize("offer", [Offer, BalancingOffer])
def test_offer_market(offer):
    market = object()
    offer = offer('a', 10, 20, 'A', market)

    assert offer.market == market


@pytest.mark.parametrize("offer", [Offer, BalancingOffer])
def test_offer_listener_deleted(offer, called):
    offer = offer(str(uuid4()), 10, 20, 'A')
    offer.add_listener(OfferEvent.DELETED, called)
    offer_repr = repr(offer)

    del offer

    assert len(called.calls) == 1
    assert called.calls[0][0] == ()
    assert called.calls[0][1] == {'offer': offer_repr}


@pytest.mark.parametrize("offer", [Offer, BalancingOffer])
def test_offer_listener_accepted(offer, called):
    offer = offer(str(uuid4()), 10, 10, 'A')
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


@pytest.mark.parametrize("offer", [Offer, BalancingOffer])
def test_offer_listener_multiple(offer, called):
    offer = offer(str(uuid4()), 10, 10, 'A')
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
