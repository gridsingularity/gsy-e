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
from copy import deepcopy
import pendulum
from math import isclose

from d3a.constants import TIME_FORMAT
from d3a.constants import TIME_ZONE
from d3a.models.area import DEFAULT_CONFIG
from d3a.models.market.market_structures import Offer, Trade, Bid
from d3a.models.strategy.area_agents.one_sided_agent import OneSidedAgent
from d3a.models.strategy.area_agents.two_sided_pay_as_bid_agent import TwoSidedPayAsBidAgent
from d3a.models.strategy.area_agents.two_sided_pay_as_bid_engine import BidInfo
from d3a_interface.constants_limits import ConstSettings
from d3a.models.market.market_structures import MarketClearingState
from d3a.models.market import TransferFees
from d3a.models.market.grid_fees.base_model import GridFees


def teardown_function():
    ConstSettings.IAASettings.MARKET_TYPE = 1
    ConstSettings.IAASettings.PAY_AS_CLEAR_AGGREGATION_ALGORITHM = 1


transfer_fees = TransferFees(grid_fee_percentage=0, transfer_fee_const=0)


class FakeArea:
    def __init__(self, name):
        self.name = name
        self.current_tick = 10
        self.future_market = None
        self.now = pendulum.DateTime.now()
        self.transfer_fee_ratio = 0

    @property
    def config(self):
        return DEFAULT_CONFIG

    def get_future_market_from_id(self, id):
        return self.future_market


class FakeMarket:
    def __init__(self, offers, bids=[], m_id=123, transfer_fees=transfer_fees, name=None):
        self.name = name
        self.id = m_id
        self.offers = {o.id: o for o in offers}
        self._bids = bids
        self.bids = {bid.id: bid for bid in self._bids}
        self.offer_call_count = 0
        self.bid_call_count = 0
        self.forwarded_offer_id = 'fwd'
        self.forwarded_bid_id = 'fwd_bid_id'
        self.calls_energy = []
        self.calls_energy_bids = []
        self.calls_offers = []
        self.calls_bids = []
        self.calls_bids_price = []
        self.time_slot = pendulum.now(tz=TIME_ZONE)
        self.time_slot_str = self.time_slot.format(TIME_FORMAT)
        self.state = MarketClearingState()
        self.transfer_fee_ratio = transfer_fees.grid_fee_percentage
        self.transfer_fee_const = transfer_fees.transfer_fee_const

    @property
    def sorted_offers(self):
        return list(sorted(self.offers.values(), key=lambda b: b.price / b.energy))

    def get_bids(self):
        return self.bids

    def set_time_slot(self, timeslot):
        self.time_slot = timeslot

    def accept_offer(self, offer_or_id, buyer, *, energy=None, time=None, already_tracked=False,
                     trade_rate: float = None, trade_bid_info=None, buyer_origin=None):
        offer = offer_or_id
        self.calls_energy.append(energy)
        self.calls_offers.append(offer)
        if energy < offer.energy:
            residual_energy = offer.energy - energy
            residual = Offer('res', offer.price, residual_energy, offer.seller,
                             seller_origin='res')
            traded = Offer(offer.id, offer.price, energy, offer.seller, seller_origin='res')
            return Trade('trade_id', time, traded, traded.seller, buyer, residual,
                         seller_origin=offer.seller_origin, buyer_origin=buyer_origin)
        else:
            return Trade('trade_id', time, offer, offer.seller, buyer,
                         seller_origin=offer.seller_origin, buyer_origin=buyer_origin)

    def accept_bid(self, bid, energy, seller, buyer=None, *, time=None, trade_rate: float = None,
                   trade_offer_info=None, already_tracked=False, seller_origin=None):
        self.calls_energy_bids.append(energy)
        self.calls_bids.append(bid)
        self.calls_bids_price.append(bid.price)
        if trade_rate is None:
            trade_rate = bid.price / bid.energy
        else:
            assert trade_rate <= (bid.price / bid.energy)

        market_bid = [b for b in self._bids if b.id == bid.id][0]
        if energy < market_bid.energy:
            residual_energy = bid.energy - energy
            residual = Bid('res', bid.price, residual_energy, bid.buyer, seller,
                           buyer_origin='res')
            traded = Bid(bid.id, (trade_rate * energy), energy, bid.buyer, seller,
                         buyer_origin='res')
            return Trade('trade_id', time, traded, traded.seller, bid.buyer, residual,
                         buyer_origin=bid.buyer_origin, seller_origin=seller_origin)
        else:
            traded = Bid(bid.id, (trade_rate * energy), energy, bid.buyer, seller,
                         buyer_origin=bid.id)
            return Trade('trade_id', time, traded, traded.seller, bid.buyer,
                         buyer_origin=bid.buyer_origin, seller_origin=seller_origin)

    def delete_offer(self, *args):
        pass

    def delete_bid(self, *args):
        pass

    def _update_new_offer_price_with_fee(self, offer_price, original_offer_price, energy):
        return offer_price \
            + self.transfer_fee_ratio * original_offer_price \
            + self.transfer_fee_const * energy

    def _update_new_bid_price_with_fee(self, bid_price, original_bid_price):
        return GridFees.update_incoming_bid_with_fee(bid_price, original_bid_price,
                                                     self.transfer_fee_ratio)

    def offer(self, price: float, energy: float, seller: str, offer_id=None,
              original_offer_price=None, dispatch_event=True, seller_origin=None,
              adapt_price_with_fees=True) -> Offer:
        self.offer_call_count += 1

        if original_offer_price is None:
            original_offer_price = price
        if offer_id is None:
            offer_id = "uuid"
        if adapt_price_with_fees:
            price = self._update_new_offer_price_with_fee(price, original_offer_price, energy)
        offer = Offer(offer_id, price, energy, seller, original_offer_price,
                      seller_origin=seller_origin)
        self.offers[offer.id] = deepcopy(offer)
        self.forwarded_offer = deepcopy(offer)

        return offer

    def dispatch_market_offer_event(self, offer):
        pass

    def bid(self, price: float, energy: float, buyer: str, seller: str,
            bid_id: str = None, original_bid_price=None, buyer_origin=None,
            adapt_price_with_fees=True):
        self.bid_call_count += 1

        if original_bid_price is None:
            original_bid_price = price

        if bid_id is None:
            bid_id = "uuid"

        if adapt_price_with_fees:
            price = self._update_new_bid_price_with_fee(price, original_bid_price)

        bid = Bid(bid_id, price, energy, buyer, seller,
                  original_bid_price=original_bid_price,
                  buyer_origin=buyer_origin)
        self._bids.append(bid)
        self.forwarded_bid = bid

        return bid

    def split_offer(self, original_offer, energy, orig_offer_price):
        self.offers.pop(original_offer.id, None)
        # same offer id is used for the new accepted_offer
        accepted_offer = self.offer(offer_id=original_offer.id,
                                    price=original_offer.price * (energy / original_offer.energy),
                                    energy=energy,
                                    seller=original_offer.seller,
                                    dispatch_event=False,
                                    seller_origin=original_offer.seller_origin)

        residual_price = (1 - energy / original_offer.energy) * original_offer.price
        residual_energy = original_offer.energy - energy
        original_residual_price = \
            ((original_offer.energy - energy) / original_offer.energy) * orig_offer_price

        residual_offer = self.offer(price=residual_price,
                                    energy=residual_energy,
                                    seller=original_offer.seller,
                                    original_offer_price=original_residual_price,
                                    dispatch_event=False,
                                    seller_origin=original_offer.seller_origin,
                                    adapt_price_with_fees=False)

        return accepted_offer, residual_offer

    def split_bid(self, original_bid, energy, orig_bid_price):
        self.offers.pop(original_bid.id, None)
        # same offer id is used for the new accepted_offer
        accepted_bid = self.bid(bid_id=original_bid.id,
                                buyer=original_bid.buyer,
                                price=original_bid.price * (energy / original_bid.energy),
                                energy=energy,
                                seller=original_bid.seller,
                                buyer_origin=original_bid.buyer_origin)
        residual_price = (1 - energy / original_bid.energy) * original_bid.price
        residual_energy = original_bid.energy - energy
        original_residual_price = \
            ((original_bid.energy - energy) / original_bid.energy) * orig_bid_price

        residual_bid = self.bid(price=residual_price,
                                buyer=original_bid.buyer,
                                energy=residual_energy,
                                seller=original_bid.seller,
                                original_bid_price=original_residual_price,
                                buyer_origin=original_bid.buyer_origin,
                                adapt_price_with_fees=False)
        return accepted_bid, residual_bid


@pytest.fixture
def iaa():
    lower_market = FakeMarket([Offer('id', 1, 1, 'other')])
    higher_market = FakeMarket([Offer('id2', 3, 3, 'owner'), Offer('id3', 0.5, 1, 'owner')])
    owner = FakeArea('owner')
    iaa = OneSidedAgent(owner=owner,
                        higher_market=higher_market,
                        lower_market=lower_market)
    iaa.event_tick()
    iaa.owner.current_tick = 14
    iaa.event_tick()
    return iaa


@pytest.fixture
def iaa_grid_fee():
    lower_market = FakeMarket([Offer('id', 1, 1, 'other')],
                              transfer_fees=TransferFees(grid_fee_percentage=0.1,
                                                         transfer_fee_const=2))
    higher_market = FakeMarket([Offer('id2', 3, 3, 'owner'), Offer('id3', 0.5, 1, 'owner')],
                               transfer_fees=TransferFees(grid_fee_percentage=0.1,
                                                          transfer_fee_const=2))
    owner = FakeArea('owner')
    iaa = OneSidedAgent(owner=owner,
                        higher_market=higher_market,
                        lower_market=lower_market)
    iaa.event_tick()
    iaa.owner.current_tick = 14
    iaa.event_tick()
    return iaa


def test_iaa_forwards_offers(iaa):
    assert iaa.lower_market.offer_call_count == 2
    assert iaa.higher_market.offer_call_count == 1


def test_iaa_forwarded_offers_complied_to_transfer_fee(iaa_grid_fee):
    source_offer = [o for o in iaa_grid_fee.lower_market.sorted_offers if o.id == "id"][0]
    target_offer = [o for o in iaa_grid_fee.higher_market.sorted_offers if o.id == "uuid"][0]
    earned_iaa_fee = target_offer.price - source_offer.price
    expected_iaa_fee = iaa_grid_fee.higher_market.transfer_fee_ratio + \
        iaa_grid_fee.higher_market.transfer_fee_const
    assert earned_iaa_fee == expected_iaa_fee


def test_iaa_event_trade_deletes_forwarded_offer_when_sold(iaa, called):
    iaa.lower_market.delete_offer = called
    iaa.event_trade(trade=Trade('trade_id',
                                pendulum.now(tz=TIME_ZONE),
                                iaa.higher_market.offers['id3'],
                                'owner',
                                'someone_else'),
                    market_id=iaa.higher_market.id)
    assert len(iaa.lower_market.delete_offer.calls) == 1


@pytest.fixture
def iaa_bid():
    ConstSettings.IAASettings.MARKET_TYPE = 2
    lower_market = FakeMarket([], [Bid('id', 1, 1, 'this', 'other', 1, buyer_origin='id')])
    higher_market = FakeMarket([], [Bid('id2', 1, 1, 'child', 'owner', 1, buyer_origin='id2'),
                                    Bid('id3', 0.5, 1, 'child', 'owner', 1, buyer_origin='id3')])
    owner = FakeArea('owner')

    iaa = TwoSidedPayAsBidAgent(owner=owner,
                                higher_market=higher_market,
                                lower_market=lower_market)
    iaa.event_tick()
    iaa.owner.current_tick = 14
    iaa.event_tick()
    yield iaa


def test_iaa_forwards_bids(iaa_bid):
    assert iaa_bid.lower_market.bid_call_count == 2
    assert iaa_bid.higher_market.bid_call_count == 1


def test_iaa_does_not_forward_bids_if_the_IAA_name_is_the_same_as_the_target_market(iaa_bid):
    assert iaa_bid.lower_market.bid_call_count == 2
    assert iaa_bid.higher_market.bid_call_count == 1
    engine = next(filter(lambda e: e.name == 'Low -> High', iaa_bid.engines))
    engine.owner.name = "TARGET MARKET"
    iaa_bid.higher_market.name = "TARGET MARKET"
    bid = Bid('id', 1, 1, 'this', 'other')
    engine._forward_bid(bid)
    assert iaa_bid.lower_market.bid_call_count == 2
    assert iaa_bid.higher_market.bid_call_count == 1


def test_iaa_forwarded_bids_adhere_to_iaa_overhead(iaa_bid):
    assert iaa_bid.higher_market.bid_call_count == 1
    expected_price = \
        list(iaa_bid.lower_market.bids.values())[-1].price * \
        (1 - iaa_bid.lower_market.transfer_fee_ratio)
    assert iaa_bid.higher_market.forwarded_bid.price == expected_price


@pytest.mark.parametrize("iaa_fee", [0.1, 0, 0.5, 0.75, 0.05, 0.02, 0.03])
def test_iaa_forwards_offers_according_to_percentage(iaa_fee):
    ConstSettings.IAASettings.MARKET_TYPE = 2
    lower_market = FakeMarket([], [Bid('id', 1, 1, 'this', 'other', 1)],
                              transfer_fees=TransferFees(grid_fee_percentage=iaa_fee,
                                                         transfer_fee_const=0),
                              name="FakeMarket")
    higher_market = FakeMarket([], [Bid('id2', 3, 3, 'child', 'owner', 3)],
                               transfer_fees=TransferFees(grid_fee_percentage=iaa_fee,
                                                          transfer_fee_const=0),
                               name="FakeMarket")
    iaa = TwoSidedPayAsBidAgent(owner=FakeArea('owner'),
                                higher_market=higher_market,
                                lower_market=lower_market)
    iaa.event_tick()
    iaa.owner.current_tick = 14
    iaa.event_tick()

    assert iaa.higher_market.bid_call_count == 1
    assert iaa.higher_market.forwarded_bid.price == \
        list(iaa.lower_market.bids.values())[-1].price * (1 - iaa_fee)


@pytest.mark.parametrize("iaa_fee_const", [0.5, 1, 5, 10])
@pytest.mark.skip("need to define if we need a constant fee")
def test_iaa_forwards_offers_according_to_constantfee(iaa_fee_const):
    ConstSettings.IAASettings.MARKET_TYPE = 2
    lower_market = FakeMarket([], [Bid('id', 15, 1, 'this', 'other', 15)],
                              transfer_fees=TransferFees(grid_fee_percentage=0,
                                                         transfer_fee_const=iaa_fee_const))
    higher_market = FakeMarket([], [Bid('id2', 35, 3, 'child', 'owner', 35)],
                               transfer_fees=TransferFees(grid_fee_percentage=0,
                                                          transfer_fee_const=iaa_fee_const))
    iaa = TwoSidedPayAsBidAgent(owner=FakeArea('owner'),
                                higher_market=higher_market,
                                lower_market=lower_market)
    iaa.event_tick()
    iaa.owner.current_tick = 14
    iaa.event_tick()

    assert iaa.higher_market.bid_call_count == 1
    bid = list(iaa.lower_market.bids.values())[-1]
    assert iaa.higher_market.forwarded_bid.price == bid.price - iaa_fee_const * bid.energy


def test_iaa_event_trade_bid_deletes_forwarded_bid_when_sold(iaa_bid, called):
    iaa_bid.lower_market.delete_bid = called
    iaa_bid.event_bid_traded(
        bid_trade=Trade('trade_id',
                        pendulum.now(tz=TIME_ZONE),
                        iaa_bid.higher_market.bids['id3'],
                        'someone_else',
                        'owner'),
        market_id=iaa_bid.higher_market.id)
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
def test_iaa_event_bid_split_and_trade_correctly_populate_forwarded_bid_entries(iaa_bid, called,
                                                                                partial):
    iaa_bid.lower_market.delete_bid = called
    low_to_high_engine = iaa_bid.engines[0]
    iaa_bid._get_market_from_market_id = lambda x: low_to_high_engine.markets.target

    source_bid = list(low_to_high_engine.markets.source.bids.values())[0]
    target_bid = list(low_to_high_engine.markets.target.bids.values())[0]
    bidinfo = BidInfo(source_bid=source_bid, target_bid=target_bid)
    low_to_high_engine.forwarded_bids[source_bid.id] = bidinfo
    low_to_high_engine.forwarded_bids[target_bid.id] = bidinfo

    if partial:
        residual_energy = 0.2
        residual_id = "resid"
        original_bid = Bid(*low_to_high_engine.markets.target._bids[0])
        accepted_bid = original_bid._replace(
            price=(original_bid.energy-residual_energy) * (original_bid.price/original_bid.energy),
            energy=original_bid.energy-residual_energy)

        residual_bid = original_bid._replace(
            id=residual_id,
            price=residual_energy * (original_bid.price / original_bid.energy),
            energy=residual_energy)

        low_to_high_engine.event_bid_split(market_id=low_to_high_engine.markets.target,
                                           original_bid=original_bid,
                                           accepted_bid=accepted_bid,
                                           residual_bid=residual_bid)
        assert set(low_to_high_engine.forwarded_bids.keys()) == \
            {original_bid.id, accepted_bid.id, residual_bid.id, "uuid", "id3", "id2"}
    else:
        original_bid = low_to_high_engine.markets.target._bids[0]
        accepted_bid = deepcopy(original_bid)
        residual_bid = None

    low_to_high_engine.event_bid_traded(
        bid_trade=Trade('trade_id',
                        pendulum.now(tz=TIME_ZONE),
                        accepted_bid,
                        seller='someone_else',
                        buyer='owner',
                        residual=residual_bid))

    if partial:
        # "id" gets traded in the target market, "id2" gets split in the source market, too
        assert set(low_to_high_engine.forwarded_bids.keys()) == {residual_bid.id, "uuid", "id3"}
    else:
        # "id" and "id2" get traded in both target and source,
        # left over is id3 and its forwarded instance uuid
        assert set(low_to_high_engine.forwarded_bids.keys()) == {"uuid", "id3"}


@pytest.fixture
def iaa2():
    lower_market = FakeMarket([Offer('id', 2, 2, 'other', 2)], m_id=123)
    higher_market = FakeMarket([], m_id=234)
    owner = FakeArea('owner')
    owner.future_market = lower_market
    iaa = OneSidedAgent(owner=owner, lower_market=lower_market, higher_market=higher_market)
    iaa.event_tick()
    iaa.owner.current_tick += 2
    iaa.event_tick()
    return iaa


@pytest.fixture
def iaa_double_sided():
    from d3a_interface.constants_limits import ConstSettings
    ConstSettings.IAASettings.MARKET_TYPE = 2
    lower_market = FakeMarket(offers=[Offer('id', 2, 2, 'other', 2)],
                              bids=[Bid('bid_id', 10, 10, 'B', 'S', 10)],
                              transfer_fees=TransferFees(grid_fee_percentage=0.01,
                                                         transfer_fee_const=0))
    higher_market = FakeMarket([], [], transfer_fees=TransferFees(grid_fee_percentage=0.01,
                                                                  transfer_fee_const=0))
    owner = FakeArea('owner')
    iaa = TwoSidedPayAsBidAgent(owner=owner, lower_market=lower_market,
                                higher_market=higher_market)
    iaa.event_tick()
    iaa.owner.current_tick += 2
    iaa.event_tick()
    yield iaa


def test_iaa_event_trade_buys_accepted_offer(iaa2):
    iaa2.event_trade(trade=Trade('trade_id',
                                 pendulum.now(tz=TIME_ZONE),
                                 iaa2.higher_market.forwarded_offer,
                                 'owner',
                                 'someone_else'),
                     market_id=iaa2.higher_market.id)
    assert len(iaa2.lower_market.calls_energy) == 1


def test_iaa_event_trade_buys_accepted_bid(iaa_double_sided):
    iaa_double_sided.higher_market.forwarded_bid = \
        iaa_double_sided.higher_market.forwarded_bid
    iaa_double_sided.event_bid_traded(
        bid_trade=Trade('trade_id',
                        pendulum.now(tz=TIME_ZONE),
                        iaa_double_sided.higher_market.forwarded_bid,
                        'owner',
                        'someone_else'),
        market_id=iaa_double_sided.higher_market.id)
    assert len(iaa_double_sided.lower_market.calls_energy_bids) == 1

    expected_price = 10 * (1 - iaa_double_sided.lower_market.transfer_fee_ratio)
    assert iaa_double_sided.higher_market.forwarded_bid.price == expected_price
    assert iaa_double_sided.lower_market.calls_bids_price[-1] == 10.0


def test_iaa_event_bid_trade_increases_bid_price(iaa_double_sided):
    iaa_double_sided.event_bid_traded(
        bid_trade=Trade('trade_id',
                        pendulum.now(tz=TIME_ZONE),
                        iaa_double_sided.higher_market.forwarded_bid,
                        'owner',
                        'someone_else'),
        market_id=iaa_double_sided.higher_market.id)
    assert len(iaa_double_sided.lower_market.calls_energy_bids) == 1
    expected_price = 10 * (1 - iaa_double_sided.lower_market.transfer_fee_ratio)
    assert iaa_double_sided.higher_market.forwarded_bid.price == expected_price

    assert iaa_double_sided.lower_market.calls_bids_price[-1] == 10


def test_iaa_event_trade_buys_partial_accepted_offer(iaa2):
    total_offer = iaa2.higher_market.forwarded_offer
    accepted_offer = Offer(total_offer.id, total_offer.price, 1, total_offer.seller)
    iaa2.event_trade(trade=Trade('trade_id',
                                 pendulum.now(tz=TIME_ZONE),
                                 accepted_offer,
                                 'owner',
                                 'someone_else',
                                 'residual_offer'),
                     market_id=iaa2.higher_market.id)
    assert iaa2.lower_market.calls_energy[0] == 1


def test_iaa_event_trade_buys_partial_accepted_bid(iaa_double_sided):
    iaa_double_sided._get_market_from_market_id = lambda x: iaa_double_sided.higher_market
    original_bid = iaa_double_sided.higher_market.forwarded_bid
    accepted_bid_price = (original_bid.price/original_bid.energy) * 1
    residual_bid_price = (original_bid.price/original_bid.energy) * 0.1
    accepted_bid = Bid(original_bid.id, accepted_bid_price, 1, original_bid.buyer,
                       original_bid.seller)
    residual_bid = Bid('residual_bid', residual_bid_price, 0.1, original_bid.buyer,
                       original_bid.seller)
    iaa_double_sided.event_bid_split(market_id=iaa_double_sided.higher_market,
                                     original_bid=original_bid,
                                     accepted_bid=accepted_bid,
                                     residual_bid=residual_bid)
    iaa_double_sided.event_bid_traded(
        bid_trade=Trade('trade_id',
                        pendulum.now(tz=TIME_ZONE),
                        accepted_bid,
                        'owner',
                        'someone_else',
                        'residual_offer'),
        market_id=iaa_double_sided.higher_market.id)
    assert iaa_double_sided.lower_market.calls_energy_bids[0] == 1


def test_iaa_forwards_partial_bid_from_source_market(iaa_double_sided):
    iaa_double_sided._get_market_from_market_id = lambda x: iaa_double_sided.lower_market
    original_bid = iaa_double_sided.lower_market._bids[0]
    residual_energy = 0.1
    accepted_bid = Bid(original_bid.id, original_bid.price,
                       original_bid.energy - residual_energy, original_bid.buyer,
                       original_bid.seller, original_bid.price)
    residual_bid = Bid('residual_bid', original_bid.price, residual_energy, original_bid.buyer,
                       original_bid.seller, original_bid.price)
    iaa_double_sided.usable_bid = lambda s: True
    iaa_double_sided.event_bid_split(market_id=iaa_double_sided.lower_market,
                                     original_bid=original_bid,
                                     accepted_bid=accepted_bid,
                                     residual_bid=residual_bid)
    assert isclose(iaa_double_sided.higher_market.forwarded_bid.energy, residual_energy)


def test_iaa_event_offer_split_and_trade_correctly_populate_forwarded_offer_entries(iaa2):
    residual_offer_id = 'res_id'
    original_offer_id = 'id'
    original = iaa2.higher_market.forwarded_offer
    assert original.energy == 2
    accepted = Offer(original.id, 1, 1, original.seller)
    residual = Offer(residual_offer_id, 1, 1, original.seller)

    iaa2.event_offer_split(market_id=iaa2.higher_market.id,
                           original_offer=original,
                           accepted_offer=accepted,
                           residual_offer=residual)
    engine = next((e for e in iaa2.engines if residual_offer_id in e.forwarded_offers), None)
    assert engine is not None, "Residual of forwarded offers not found in forwarded_offers"

    # after the split event:
    # all three offer ids are part of the forwarded_offer member
    assert set(engine.forwarded_offers.keys()) == {residual_offer_id, original_offer_id,
                                                   'uuid'}
    # and the accepted offer was added
    assert engine.forwarded_offers[original_offer_id].target_offer.energy == accepted.energy
    # and the residual offer was added
    assert engine.forwarded_offers[residual_offer_id].target_offer.energy == accepted.energy

    iaa2.event_trade(trade=Trade('trade_id',
                                 pendulum.now(tz=TIME_ZONE),
                                 accepted,
                                 'owner',
                                 'someone_else',
                                 residual),
                     market_id=iaa2.lower_market.id)

    # after the trade event:
    # the forwarded_offers only contain the residual offer
    assert set(engine.forwarded_offers.keys()) == {residual_offer_id}
    offer_info = engine.forwarded_offers[residual_offer_id]
    assert offer_info.source_offer.id == "uuid"
    assert offer_info.target_offer.id == residual_offer_id
