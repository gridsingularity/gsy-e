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
        self.forwarded_offer_id = 'fwd'
        self.calls_energy = []

    @property
    def offers(self):
        return {offer.id: offer for offer in self.sorted_offers}

    @property
    def time_slot(self):
        return datetime.now()

    def accept_offer(self, offer, buyer, *, energy=None, time=None):
        self.calls_energy.append(energy)
        if energy < offer.energy:
            residual_energy = offer.energy - energy
            residual = Offer('res', offer.price, residual_energy, offer.seller, offer.market)
            traded = Offer(offer.id, offer.price, energy, offer.seller, offer.market)
            return Trade('trade_id', time, traded, traded.seller, buyer, residual)
        else:
            return Trade('trade_id', time, offer, offer.seller, buyer)

    def delete_offer(self, *args):
        pass

    def offer(self, price, energy, seller):
        self.offer_count += 1
        self.forwarded_offer = Offer(self.forwarded_offer_id, price, energy, seller, market=self)
        return self.forwarded_offer


@pytest.fixture
def iaa():
    lower_market = FakeMarket([Offer('id', 1, 1, 'other')])
    higher_market = FakeMarket([Offer('id2', 3, 3, 'owner'), Offer('id3', 0.5, 1, 'owner')])
    owner = FakeArea('owner')
    iaa = InterAreaAgent(owner=owner,
                         higher_market=higher_market,
                         lower_market=lower_market,
                         transfer_fee_pct=5)
    iaa.event_tick(area=iaa.owner)
    iaa.owner.current_tick = 14
    iaa.event_tick(area=iaa.owner)
    return iaa


def test_iaa_forwards_offers(iaa):
    assert iaa.lower_market.offer_count == 2
    assert iaa.higher_market.offer_count == 1


def test_iaa_forwarded_offers_complied_to_transfer_fee_percentage(iaa):
    iaa_per_fee = ((iaa.higher_market.forwarded_offer.price -
                    iaa.lower_market.sorted_offers[-1].price) /
                   iaa.lower_market.sorted_offers[-1].price)
    assert round(iaa_per_fee, 2) == (5/100)


def test_iaa_event_trade_deletes_forwarded_offer_when_sold(iaa, called):
    iaa.lower_market.delete_offer = called
    iaa.event_trade(trade=Trade('trade_id',
                                datetime.now(),
                                iaa.higher_market.offers['id3'],
                                'owner',
                                'someone_else'),
                    market=iaa.higher_market)
    assert len(iaa.lower_market.delete_offer.calls) == 1


@pytest.fixture
def iaa2():
    lower_market = FakeMarket([Offer('id', 2, 2, 'other')])
    higher_market = FakeMarket([])
    owner = FakeArea('owner')
    iaa = InterAreaAgent(owner=owner, lower_market=lower_market, higher_market=higher_market)
    iaa.event_tick(area=iaa.owner)
    iaa.owner.current_tick += 2
    iaa.event_tick(area=iaa.owner)
    return iaa


def test_iaa_event_trade_buys_accepted_offer(iaa2):
    iaa2.event_trade(trade=Trade('trade_id',
                                 datetime.now(),
                                 iaa2.higher_market.forwarded_offer,
                                 'owner',
                                 'someone_else'),
                     market=iaa2.higher_market)
    assert len(iaa2.lower_market.calls_energy) == 1


def test_iaa_event_trade_buys_partial_accepted_offer(iaa2):
    total_offer = iaa2.higher_market.forwarded_offer
    accepted_offer = Offer(total_offer.id, total_offer.price, 1, total_offer.seller)
    iaa2.event_trade(trade=Trade('trade_id',
                                 datetime.now(),
                                 accepted_offer,
                                 'owner',
                                 'someone_else',
                                 'residual_offer'),
                     market=iaa2.higher_market)
    assert iaa2.lower_market.calls_energy[0] == 1


def test_iaa_forwards_partial_offer_from_source_market(iaa2):
    full_offer = iaa2.lower_market.sorted_offers[0]
    residual_offer = Offer('residual', 2, 1.4, 'other')
    iaa2.event_offer_changed(market=iaa2.lower_market,
                             existing_offer=full_offer,
                             new_offer=residual_offer)
    assert iaa2.higher_market.forwarded_offer.energy == 1.4


@pytest.fixture
def iaa3(iaa2):
    fwd_offer = iaa2.higher_market.forwarded_offer
    fwd_residual = Offer('res_fwd', fwd_offer.price, 1, fwd_offer.seller)
    iaa2.event_offer_changed(market=iaa2.higher_market,
                             existing_offer=fwd_offer,
                             new_offer=fwd_residual)
    iaa2.event_trade(trade=Trade('trade_id',
                                 datetime.now(),
                                 Offer(fwd_offer.id, fwd_offer.price, 1, fwd_offer.seller),
                                 'owner',
                                 'someone_else',
                                 fwd_residual),
                     market=iaa2.higher_market)
    return iaa2


def test_iaa_event_trade_forwards_residual_offer(iaa3):
    engine = next((e for e in iaa3.engines if 'res_fwd' in e.offered_offers), None)
    assert engine is not None, "Residual of forwarded offers not found in offered_offers"
    assert engine.offer_age['res'] == 10
    offer_info = engine.offered_offers['res_fwd']
    assert offer_info.source_offer.id == 'res'
