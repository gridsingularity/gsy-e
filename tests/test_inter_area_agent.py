import pytest

from datetime import datetime

from d3a.models.market import Offer, Trade
from d3a.models.strategy.inter_area import InterAreaAgent


class FakeArea:
    def __init__(self, name):
        self.name = name
        self.current_tick = 10


class FakeMarket:
    def __init__(self, sorted_offers):
        self.sorted_offers = sorted_offers
        self.offer_count = 0

    @property
    def offers(self):
        return {offer.id: offer for offer in self.sorted_offers}

    @property
    def time_slot(self):
        return datetime.now()

    def accept_offer(self, *args):
        pass

    def delete_offer(self, *args):
        pass

    def offer(self, price, energy, seller):
        self.offer_count += 1
        self.forwarded_offer = Offer('fwd', 1, 1, seller, market=self)
        return self.forwarded_offer


@pytest.fixture
def iaa():
    lower_market = FakeMarket([Offer('id', 1, 1, 'other')])
    higher_market = FakeMarket([Offer('id2', 3, 3, 'owner'), Offer('id3', 0.5, 1, 'owner')])
    owner = FakeArea('owner')
    iaa = InterAreaAgent(owner=owner, higher_market=higher_market, lower_market=lower_market)
    iaa.event_tick(area=iaa.owner)
    iaa.owner.current_tick = 14
    iaa.event_tick(area=iaa.owner)
    return iaa


def test_iaa_forwards_offers(iaa):
    assert iaa.lower_market.offer_count == 2
    assert iaa.higher_market.offer_count == 1


def test_iaa_event_trade_doesnt_deletes_forwarded_offer_when_sold(iaa, called):
    iaa.lower_market.delete_offer = called
    iaa.event_trade(trade=Trade('trade_id',
                                datetime.now(),
                                iaa.higher_market.offers['id3'],
                                'owner',
                                'someone_else'),
                    market=iaa.higher_market)
    assert len(iaa.lower_market.delete_offer.calls) == 1


@pytest.mark.skip('fix: offer is not recognized')
def test_iaa_event_trade_buys_accepted_offer(iaa, called):
    iaa.lower_market.accept_offer = called
    iaa.event_trade(trade=Trade('trade_id',
                                datetime.now(),
                                iaa.higher_market.forwarded_offer,
                                'owner',
                                'someone_else'),
                    market=iaa.higher_market)
    assert len(iaa.lower_market.accept_offer.calls) == 1
