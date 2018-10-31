from d3a.models.market.market_structures import Bid


def test_offer_id_stringified():
    market = object()
    bid = Bid(object(), 10, 20, 'A', 'B', market)

    assert isinstance(bid.id, str)
    assert "<object object at" in bid.id


def test_offer_market():
    market = object()
    bid = Bid('a', 10, 20, 'A', 'B', market)

    assert bid.market == market
