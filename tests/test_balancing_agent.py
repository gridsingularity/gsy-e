import pytest

import pendulum
from d3a import TIME_ZONE
from d3a.exceptions import InvalidBalancingTradeException
from d3a.models.market import BalancingOffer, BalancingTrade, Offer, Trade
from d3a.models.strategy.inter_area import BalancingAgent
from d3a.models.strategy.const import ConstSettings
from tests.test_inter_area_agent import FakeMarket


class FakeArea:
    def __init__(self, name):
        self.name = name
        self.current_tick = 10
        self.balancing_spot_trade_ratio = ConstSettings.BALANCING_SPOT_TRADE_RATIO


class FakeBalancingMarket:
    def __init__(self, sorted_offers):
        self.sorted_offers = sorted_offers
        self.forwarded_offer_id = 'fwd'
        self.area = FakeArea("fake_area")
        self.unmatched_energy_upward = 0
        self.unmatched_energy_downward = 0
        self.cumulative_energy_traded_upward = 0
        self.cumulative_energy_traded_downward = 0
        self._timeslot = pendulum.now(tz=TIME_ZONE)

    @property
    def time_slot(self):
        return self._timeslot

    def accept_offer(self, offer_or_id, buyer, energy=None, time=None, price_drop=False):
        if time is None:
            time = self.time_slot
        offer = offer_or_id
        if (offer.energy > 0 and energy < 0) or (offer.energy < 0 and energy > 0):
            raise InvalidBalancingTradeException("BalancingOffer and energy "
                                                 "are not compatible")

        if abs(energy) < abs(offer.energy):
            residual_energy = offer.energy - energy
            residual = BalancingOffer('res', offer.price, residual_energy,
                                      offer.seller, offer.market)
            traded = BalancingOffer(offer.id, offer.price, energy, offer.seller, offer.market)
            return BalancingTrade('trade_id', time, traded, traded.seller, buyer, residual)
        else:
            return BalancingTrade('trade_id', time, offer, offer.seller, buyer)


@pytest.fixture
def baa():
    lower_market = FakeBalancingMarket([BalancingOffer('id', 2, 2, 'other'),
                                        BalancingOffer('id', 2, -2, 'other')])
    higher_market = FakeBalancingMarket([])
    owner = FakeArea('owner')
    baa = BalancingAgent(owner=owner, lower_market=lower_market, higher_market=higher_market)
    return baa


def test_baa_event_trade(baa):
    trade = Trade('trade_id',
                  baa.lower_market.time_slot,
                  Offer('A', 2, 2, 'B'),
                  'someone_else',
                  'IAA owner')
    expected_balancing_trade = trade.offer.energy * baa.balancing_spot_trade_ratio
    fake_spot_market = FakeMarket(15)
    fake_spot_market.set_time_slot(baa.lower_market.time_slot)
    baa.event_trade(trade=trade,
                    market=fake_spot_market)
    assert baa.lower_market.cumulative_energy_traded_upward == expected_balancing_trade
    assert baa.lower_market.cumulative_energy_traded_downward == expected_balancing_trade
    assert baa.lower_market.unmatched_energy_upward == 0
    assert baa.lower_market.unmatched_energy_downward == 0


@pytest.fixture
def baa2():
    lower_market = FakeBalancingMarket([BalancingOffer('id', 2, 0.2, 'other'),
                                        BalancingOffer('id', 2, -0.2, 'other')])
    higher_market = FakeBalancingMarket([])
    owner = FakeArea('owner')
    baa = BalancingAgent(owner=owner, lower_market=lower_market, higher_market=higher_market)
    return baa


def test_baa_unmatched_event_trade(baa2):
    trade = Trade('trade_id',
                  pendulum.now(tz=TIME_ZONE),
                  Offer('A', 2, 2, 'B'),
                  'someone_else',
                  'IAA owner')
    expected_balancing_trade = (baa2.lower_market.sorted_offers)[0].energy
    fake_spot_market = FakeMarket(15)
    fake_spot_market.set_time_slot(baa2.lower_market.time_slot)
    baa2.event_trade(trade=trade,
                     market=fake_spot_market)
    assert baa2.lower_market.cumulative_energy_traded_upward == expected_balancing_trade
    assert baa2.lower_market.cumulative_energy_traded_downward == expected_balancing_trade
    assert baa2.lower_market.unmatched_energy_upward != 0
    assert baa2.lower_market.unmatched_energy_downward != 0
