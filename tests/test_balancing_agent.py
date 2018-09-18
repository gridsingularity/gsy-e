import pytest

from datetime import datetime

from d3a.models.market import BalancingOffer, BalancingTrade
from d3a.models.strategy.inter_area import BalancingAgent
from d3a.models.strategy.const import ConstSettings

from d3a.device_registry import DeviceRegistry
DeviceRegistry.REGISTRY = {
    "A": {"balancing rates": (23, 25)},
    "someone": {"balancing rates": (23, 25)},
    "seller": {"balancing rates": (23, 25)},
}


class FakeArea:
    def __init__(self, name):
        self.name = name
        self.current_tick = 10
        self.balancing_spot_trade_ratio = ConstSettings.BALANCING_SPOT_TRADE_RATIO


class FakeBalancingMarket:
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
        self.balancing_energy = 0
        self.cumulative_energy_traded = 0

    @property
    def offers(self):
        return {offer.id: offer for offer in self.sorted_offers}

    @property
    def time_slot(self):
        return datetime.now()

    def accept_balancing_offer(self, offer, buyer, energy=None, time=None, price_drop=False):
        self.calls_energy.append(energy)
        self.calls_offers.append(offer)

        if time is None:
            time = self.time_slot

        if energy < offer.energy:
            residual_energy = offer.energy - energy
            residual = BalancingOffer('res', offer.price, residual_energy,
                                      offer.seller, offer.market)
            traded = BalancingOffer(offer.id, offer.price, energy, offer.seller, offer.market)
            return BalancingTrade('trade_id', time, traded, traded.seller, buyer, residual)
        else:
            return BalancingTrade('trade_id', time, offer, offer.seller, buyer)

    def delete_offer(self, *args):
        pass

    def balancing_offer(self, price, energy, seller):
        self.offer_count += 1
        self.forwarded_offer = \
            BalancingOffer(self.forwarded_offer_id, price, energy, seller, market=self)
        return self.forwarded_offer

    def offer(self, price, energy, seller):
        self.offer_count += 1
        self.forwarded_offer = \
            BalancingOffer(self.forwarded_offer_id, price, energy, seller, market=self)
        return self.forwarded_offer


@pytest.fixture
def baa():
    lower_market = FakeBalancingMarket([BalancingOffer('id', 2, 2, 'other')])
    higher_market = FakeBalancingMarket([])
    owner = FakeArea('owner')
    baa = BalancingAgent(owner=owner, lower_market=lower_market, higher_market=higher_market)
    baa.event_tick(area=baa.owner)
    baa.owner.current_tick += 2
    baa.event_tick(area=baa.owner)
    return baa


def test_baa_event_trade(baa):
    expected_balancing_trade = baa.lower_market.sorted_offers[0].energy * \
                               baa.balancing_spot_trade_ratio
    baa.event_trade(trade=BalancingTrade('trade_id',
                                         datetime.now(),
                                         baa.higher_market.forwarded_offer,
                                         'owner',
                                         'someone_else'),
                    market=baa.higher_market)
    assert len(baa.lower_market.calls_energy) == 1
    assert baa.lower_market.cumulative_energy_traded == expected_balancing_trade
