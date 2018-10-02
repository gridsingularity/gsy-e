import pytest

import pendulum

from d3a import TIME_ZONE
from d3a.models.market import Offer, Trade, Bid
from d3a.models.strategy.inter_area import InterAreaAgent, BidInfo, OfferInfo
from d3a.models.strategy.const import ConstSettings


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
        self.calls_offers = []
        self.calls_bids = []
        self.calls_bids_price = []
        self.area = FakeArea("fake_area")
        self.time_slot = pendulum.now(tz=TIME_ZONE)

    def set_time_slot(self, timeslot):
        self.time_slot = timeslot

    @property
    def offers(self):
        return {offer.id: offer for offer in self.sorted_offers}

    @property
    def bids(self):
        return {bid.id: bid for bid in self._bids}

    def accept_offer(self, offer, buyer, *, energy=None, time=None, price_drop=False):
        self.calls_energy.append(energy)
        self.calls_offers.append(offer)
        if energy < offer.energy:
            residual_energy = offer.energy - energy
            residual = Offer('res', offer.price, residual_energy, offer.seller, offer.market)
            traded = Offer(offer.id, offer.price, energy, offer.seller, offer.market)
            return Trade('trade_id', time, traded, traded.seller, buyer, residual)
        else:
            return Trade('trade_id', time, offer, offer.seller, buyer)

    def accept_bid(self, bid, energy, seller, buyer=None, track_bid=True, *,
                   time=None, price_drop=True):
        self.calls_energy_bids.append(energy)
        self.calls_bids.append(bid)
        self.calls_bids_price.append(bid.price)
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

    def offer(self, price, energy, seller, agent=False):
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
                                pendulum.now(tz=TIME_ZONE),
                                iaa.higher_market.offers['id3'],
                                'owner',
                                'someone_else'),
                    market=iaa.higher_market)
    assert len(iaa.lower_market.delete_offer.calls) == 1


@pytest.fixture
def iaa_bid():
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
    ConstSettings.INTER_AREA_AGENT_MARKET_TYPE = 1


def test_iaa_forwards_bids(iaa_bid):
    assert iaa_bid.lower_market.bid_count == 2
    assert iaa_bid.higher_market.bid_count == 1


def test_iaa_does_not_forward_bids_if_the_IAA_name_is_the_same_as_the_target_market(iaa_bid):
    assert iaa_bid.lower_market.bid_count == 2
    assert iaa_bid.higher_market.bid_count == 1
    engine = next(filter(lambda e: e.name == 'Low -> High', iaa_bid.engines))
    engine.owner.name = "TARGET MARKET"
    iaa_bid.higher_market.area.name = "TARGET MARKET"
    bid = Bid('id', 1, 1, 'this', 'other')
    engine._forward_bid(bid)
    assert iaa_bid.lower_market.bid_count == 2
    assert iaa_bid.higher_market.bid_count == 1


def test_iaa_forwarded_bids_adhere_to_iaa_overhead(iaa_bid):
    assert iaa_bid.higher_market.bid_count == 1
    assert iaa_bid.higher_market.forwarded_bid.price / (1 + (iaa_bid.transfer_fee_pct / 100)) == \
        list(iaa_bid.lower_market.bids.values())[-1].price


@pytest.mark.parametrize("iaa_fee", [10, 0, 50, 75, 5, 2, 3])
def test_iaa_forwards_offers_according_to_percentage(iaa_fee):
    ConstSettings.INTER_AREA_AGENT_MARKET_TYPE = 2
    lower_market = FakeMarket([], [Bid('id', 1, 1, 'this', 'other')])
    higher_market = FakeMarket([], [Bid('id2', 3, 3, 'child', 'owner')])
    iaa = InterAreaAgent(owner=FakeArea('owner'),
                         higher_market=higher_market,
                         lower_market=lower_market,
                         transfer_fee_pct=iaa_fee)
    iaa.event_tick(area=iaa.owner)
    assert iaa.higher_market.bid_count == 1
    assert iaa.higher_market.forwarded_bid.price / (1 + (iaa_fee / 100)) == \
        list(iaa.lower_market.bids.values())[-1].price
    ConstSettings.INTER_AREA_AGENT_MARKET_TYPE = 1


def test_iaa_event_trade_bid_deletes_forwarded_bid_when_sold(iaa_bid, called):
    iaa_bid.lower_market.delete_bid = called
    iaa_bid.event_bid_traded(
        bid_trade=Trade('trade_id',
                        pendulum.now(tz=TIME_ZONE),
                        iaa_bid.higher_market.bids['id3'],
                        'someone_else',
                        'owner'),
        market=iaa_bid.higher_market)
    assert len(iaa_bid.lower_market.delete_bid.calls) == 1


def test_iaa_event_trade_bid_does_not_delete_forwarded_bid_of_counterpart(iaa_bid, called):
    iaa_bid.lower_market.delete_bid = called
    high_to_low_engine = iaa_bid.engines[1]
    high_to_low_engine.event_bid_traded(
        bid_trade=Trade('trade_id',
                        pendulum.now(tz=TIME_ZONE),
                        iaa_bid.higher_market.bids['id3'],
                        seller='owner',
                        buyer='someone_else'))
    assert len(iaa_bid.lower_market.delete_bid.calls) == 0


@pytest.mark.parametrize("partial", [True, False])
def test_iaa_event_trade_bid_does_not_update_forwarded_bids_on_partial(iaa_bid, called, partial):
    iaa_bid.lower_market.delete_bid = called
    low_to_high_engine = iaa_bid.engines[0]
    source_bid = list(low_to_high_engine.markets.source.bids.values())[0]
    target_bid = list(low_to_high_engine.markets.target.bids.values())[0]
    bidinfo = BidInfo(source_bid=source_bid, target_bid=target_bid)
    low_to_high_engine.forwarded_bids[source_bid.id] = bidinfo
    low_to_high_engine.forwarded_bids[target_bid.id] = bidinfo
    low_to_high_engine.event_bid_traded(
        bid_trade=Trade('trade_id',
                        pendulum.now(tz=TIME_ZONE),
                        low_to_high_engine.markets.target.bids[target_bid.id],
                        seller='someone_else',
                        buyer='owner',
                        residual=partial))
    if not partial:
        assert source_bid.id not in low_to_high_engine.forwarded_bids
        assert target_bid.id not in low_to_high_engine.forwarded_bids
    else:
        assert source_bid.id in low_to_high_engine.forwarded_bids
        assert target_bid.id in low_to_high_engine.forwarded_bids


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
    iaa.engines[0]._match_offers_bids = lambda: None
    iaa.engines[1]._match_offers_bids = lambda: None
    iaa.event_tick(area=iaa.owner)
    yield iaa
    ConstSettings.INTER_AREA_AGENT_MARKET_TYPE = 1


def test_iaa_event_trade_buys_accepted_offer(iaa2):
    iaa2.event_trade(trade=Trade('trade_id',
                                 pendulum.now(tz=TIME_ZONE),
                                 iaa2.higher_market.forwarded_offer,
                                 'owner',
                                 'someone_else'),
                     market=iaa2.higher_market)
    assert len(iaa2.lower_market.calls_energy) == 1


def test_iaa_event_trade_buys_accepted_bid(iaa_double_sided):
    iaa_double_sided.higher_market.forwarded_bid = \
        iaa_double_sided.higher_market.forwarded_bid._replace(price=20)
    iaa_double_sided.event_bid_traded(
        bid_trade=Trade('trade_id',
                        pendulum.now(tz=TIME_ZONE),
                        iaa_double_sided.higher_market.forwarded_bid,
                        'owner',
                        'someone_else',
                        price_drop=False),
        market=iaa_double_sided.higher_market)
    assert len(iaa_double_sided.lower_market.calls_energy_bids) == 1

    assert iaa_double_sided.higher_market.forwarded_bid.price == 20.0
    assert iaa_double_sided.lower_market.calls_bids_price[-1] == 10.0


def test_iaa_event_bid_trade_reduces_bid_price(iaa_double_sided):
    iaa_double_sided.higher_market.forwarded_bid = \
        iaa_double_sided.higher_market.forwarded_bid._replace(price=20.2)
    iaa_double_sided.event_bid_traded(
        bid_trade=Trade('trade_id',
                        pendulum.now(tz=TIME_ZONE),
                        iaa_double_sided.higher_market.forwarded_bid,
                        'owner',
                        'someone_else',
                        price_drop=True),
        market=iaa_double_sided.higher_market)
    assert len(iaa_double_sided.lower_market.calls_energy_bids) == 1
    assert iaa_double_sided.higher_market.forwarded_bid.price == 20.2
    assert iaa_double_sided.lower_market.calls_bids_price[-1] == 20.0


def test_iaa_event_trade_buys_partial_accepted_offer(iaa2):
    total_offer = iaa2.higher_market.forwarded_offer
    accepted_offer = Offer(total_offer.id, total_offer.price, 1, total_offer.seller)
    iaa2.event_trade(trade=Trade('trade_id',
                                 pendulum.now(tz=TIME_ZONE),
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
        bid_trade=Trade('trade_id',
                        pendulum.now(tz=TIME_ZONE),
                        accepted_bid,
                        'owner',
                        'someone_else',
                        'residual_offer'),
        market=iaa_double_sided.higher_market)
    assert iaa_double_sided.lower_market.calls_energy_bids[0] == 1


def test_iaa_forwards_partial_offer_from_source_market(iaa2):
    full_offer = iaa2.lower_market.sorted_offers[0]
    iaa2.usable_offer = lambda s: True
    residual_offer = Offer('residual', 2, 1.4, 'other')
    iaa2.event_offer_changed(market=iaa2.lower_market,
                             existing_offer=full_offer,
                             new_offer=residual_offer)
    assert iaa2.higher_market.forwarded_offer.energy == 1.4


@pytest.fixture
def iaa_double_sided_2():
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


def test_iaa_double_sided_performs_pay_as_bid_matching(iaa_double_sided_2):
    low_high_engine = next(filter(lambda e: e.name == "Low -> High", iaa_double_sided_2.engines))

    iaa_double_sided_2.lower_market._bids = [Bid('bid_id', 9, 10, 'B', 'S')]
    matched = list(low_high_engine._perform_pay_as_bid_matching())
    assert len(matched) == 0

    iaa_double_sided_2.lower_market._bids = [Bid('bid_id', 10, 10, 'B', 'S')]
    matched = list(low_high_engine._perform_pay_as_bid_matching())
    assert len(matched) == 1
    bid, offer = matched[0]
    assert bid == list(iaa_double_sided_2.lower_market.bids.values())[0]
    assert offer == list(iaa_double_sided_2.lower_market.offers.values())[0]

    iaa_double_sided_2.lower_market._bids = [Bid('bid_id1', 11, 10, 'B', 'S'),
                                             Bid('bid_id2', 9, 10, 'B', 'S'),
                                             Bid('bid_id3', 12, 10, 'B', 'S')]
    matched = list(low_high_engine._perform_pay_as_bid_matching())
    assert len(matched) == 1
    bid, offer = matched[0]
    assert bid.id == 'bid_id3'
    assert bid.price == 12
    assert bid.energy == 10
    assert offer == list(iaa_double_sided_2.lower_market.offers.values())[0]


def test_iaa_double_sided_match_offer_bids(iaa_double_sided_2):
    iaa_double_sided_2.lower_market.calls_offers = []
    iaa_double_sided_2.lower_market.calls_bids = []
    low_high_engine = next(filter(lambda e: e.name == "Low -> High",
                                  iaa_double_sided_2.engines))
    source_bid = Bid('bid_id3', 12, 10, 'B', 'S')
    iaa_double_sided_2.lower_market._bids = [Bid('bid_id1', 11, 10, 'B', 'S'),
                                             Bid('bid_id2', 9, 10, 'B', 'S'),
                                             source_bid]

    target_bid = Bid('fwd_bid_id3', 12, 10, 'B', 'S')
    # Populate forwarded_bids and offers to test they get cleaned up afterwards
    fwd_bidinfo = BidInfo(source_bid=source_bid, target_bid=target_bid)
    low_high_engine.forwarded_bids['bid_id3'] = fwd_bidinfo
    low_high_engine.forwarded_bids['fwd_bid_id3'] = fwd_bidinfo

    source_offer = iaa_double_sided_2.lower_market.sorted_offers[0]
    target_offer = Offer('forwarded_id', 1, 1, 'other')
    fwd_offerinfo = OfferInfo(source_offer=source_offer, target_offer=target_offer)
    low_high_engine.forwarded_offers['id'] = fwd_offerinfo
    low_high_engine.forwarded_offers['forwarded_id'] = fwd_offerinfo

    low_high_engine._match_offers_bids()
    assert len(iaa_double_sided_2.lower_market.calls_offers) == 1
    offer = iaa_double_sided_2.lower_market.calls_offers[0]
    assert offer.id == 'id'
    assert offer.energy == 2
    assert offer.price == 2.4

    assert len(iaa_double_sided_2.lower_market.calls_bids) == 1
    bid = iaa_double_sided_2.lower_market.calls_bids[0]
    assert bid.id == 'bid_id3'
    assert bid.energy == 10
    assert bid.price == 12

    assert len(low_high_engine.forwarded_bids.keys()) == 0
    assert len(low_high_engine.forwarded_offers.keys()) == 0


@pytest.fixture
def iaa3(iaa2):
    fwd_offer = iaa2.higher_market.forwarded_offer
    fwd_residual = Offer('res_fwd', fwd_offer.price, 1, fwd_offer.seller)
    iaa2.event_offer_changed(market=iaa2.higher_market,
                             existing_offer=fwd_offer,
                             new_offer=fwd_residual)
    iaa2.event_trade(trade=Trade('trade_id',
                                 pendulum.now(tz=TIME_ZONE),
                                 Offer(fwd_offer.id, fwd_offer.price, 1, fwd_offer.seller),
                                 'owner',
                                 'someone_else',
                                 fwd_residual),
                     market=iaa2.higher_market)
    return iaa2


def test_iaa_event_trade_forwards_residual_offer(iaa3):
    engine = next((e for e in iaa3.engines if 'res_fwd' in e.forwarded_offers), None)
    assert engine is not None, "Residual of forwarded offers not found in forwarded_offers"
    assert engine.offer_age['res'] == 10
    offer_info = engine.forwarded_offers['res_fwd']
    assert offer_info.source_offer.id == 'res'
