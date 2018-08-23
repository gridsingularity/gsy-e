import pytest

from datetime import datetime

from d3a.models.market import Offer, Trade, Bid
from d3a.models.strategy.inter_area import InterAreaAgent


class FakeArea:
    def __init__(self, name):
        self.name = name
        self.current_tick = 10


class FakeMarket:
    def __init__(self, sorted_offers, bids=[]):
        self.sorted_offers = sorted_offers
        self._bids = bids
        self.offer_count = 0
        self.bid_count = 0
        self.forwarded_offer_id = 'fwd'
        self.forwarded_bid_id = 'fwd_bid_id'
        self.calls_energy = []
        self.calls_energy_bids = []
        self.area = FakeArea("fake_area")

    @property
    def offers(self):
        return {offer.id: offer for offer in self.sorted_offers}

    @property
    def bids(self):
        return {bid.id: bid for bid in self._bids}

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

    def accept_bid(self, bid, energy, seller, *, time=None):
        self.calls_energy_bids.append(energy)
        if energy < bid.energy:
            residual_energy = bid.energy - energy
            residual = Bid('res', bid.price, residual_energy, bid.buyer, seller, bid.market)
            traded = Bid(bid.id, bid.price, energy, bid.buyer, seller, bid.market)
            return Trade('trade_id', time, traded, traded.seller, bid.buyer, residual)
        else:
            return Trade('trade_id', time, bid, bid.seller, bid.buyer)

    def delete_offer(self, *args):
        pass

    def delete_bid(self, *args):
        pass

    def offer(self, price, energy, seller):
        self.offer_count += 1
        self.forwarded_offer = Offer(self.forwarded_offer_id, price, energy, seller, market=self)
        return self.forwarded_offer

    def bid(self, price, energy, buyer, seller):
        self.bid_count += 1
        self.forwarded_bid = Bid(self.forwarded_bid_id, price, energy, buyer, seller, market=self)
        return self.forwarded_bid


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
    assert round(iaa_per_fee, 2) == round(iaa.transfer_fee_pct/100, 2)


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
def iaa_bid():
    from d3a.models.strategy.const import ConstSettings
    ConstSettings.INTER_AREA_AGENT_MARKET_TYPE = 2
    lower_market = FakeMarket([], [Bid('id', 1, 1, 'this', 'other')])
    higher_market = FakeMarket([], [Bid('id2', 3, 3, 'child', 'owner'),
                                    Bid('id3', 0.5, 1, 'child', 'owner')])
    owner = FakeArea('owner')
    iaa = InterAreaAgent(owner=owner,
                         higher_market=higher_market,
                         lower_market=lower_market,
                         transfer_fee_pct=5)
    iaa.event_tick(area=iaa.owner)
    iaa.owner.current_tick = 14
    iaa.event_tick(area=iaa.owner)
    yield iaa
    ConstSettings.INTER_AREA_AGENT_MARKET_TYPE = 2


def test_iaa_forwards_bids(iaa_bid):
    assert iaa_bid.lower_market.bid_count == 2
    assert iaa_bid.higher_market.bid_count == 1


def test_iaa_forwarded_bids_do_not_have_overhead(iaa_bid):
    assert iaa_bid.higher_market.bid_count == 1
    assert iaa_bid.higher_market.forwarded_bid.price == \
        list(iaa_bid.lower_market.bids.values())[-1].price


def test_iaa_event_trade_bid_deletes_forwarded_bid_when_sold(iaa_bid, called):
    iaa_bid.lower_market.delete_bid = called
    iaa_bid.event_bid_traded(
        traded_bid=Trade('trade_id',
                         datetime.now(),
                         iaa_bid.higher_market.bids['id3'],
                         'owner',
                         'someone_else'),
        market=iaa_bid.higher_market)
    assert len(iaa_bid.lower_market.delete_bid.calls) == 1


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


@pytest.fixture
def iaa_double_sided():
    from d3a.models.strategy.const import ConstSettings
    ConstSettings.INTER_AREA_AGENT_MARKET_TYPE = 2
    lower_market = FakeMarket(sorted_offers=[Offer('id', 2, 2, 'other')],
                              bids=[Bid('bid_id', 10, 10, 'B', 'S')])
    higher_market = FakeMarket([], [])
    owner = FakeArea('owner')
    iaa = InterAreaAgent(owner=owner, lower_market=lower_market, higher_market=higher_market)
    iaa.event_tick(area=iaa.owner)
    yield iaa
    ConstSettings.INTER_AREA_AGENT_MARKET_TYPE = 1


def test_iaa_event_trade_buys_accepted_offer(iaa2):
    iaa2.event_trade(trade=Trade('trade_id',
                                 datetime.now(),
                                 iaa2.higher_market.forwarded_offer,
                                 'owner',
                                 'someone_else'),
                     market=iaa2.higher_market)
    assert len(iaa2.lower_market.calls_energy) == 1


def test_iaa_event_trade_buys_accepted_bid(iaa_double_sided):
    iaa_double_sided.event_bid_traded(
        traded_bid=Trade('trade_id',
                         datetime.now(),
                         iaa_double_sided.higher_market.forwarded_bid,
                         'owner',
                         'someone_else'),
        market=iaa_double_sided.higher_market)
    assert len(iaa_double_sided.lower_market.calls_energy_bids) == 1


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


def test_iaa_event_trade_buys_partial_accepted_bid(iaa_double_sided):
    total_bid = iaa_double_sided.higher_market.forwarded_bid
    accepted_bid = Bid(total_bid.id, total_bid.price, 1, total_bid.buyer, total_bid.seller)
    iaa_double_sided.event_bid_traded(
        traded_bid=Trade('trade_id',
                         datetime.now(),
                         accepted_bid,
                         'owner',
                         'someone_else',
                         'residual_offer'),
        market=iaa_double_sided.higher_market)
    assert iaa_double_sided.lower_market.calls_energy_bids[0] == 1


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
