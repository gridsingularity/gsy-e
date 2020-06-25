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

import pendulum
from d3a.constants import TIME_ZONE
from d3a.d3a_core.exceptions import InvalidBalancingTradeException
from d3a.models.market.market_structures import BalancingOffer, BalancingTrade, Offer, Trade
from d3a.models.strategy.area_agents.balancing_agent import BalancingAgent
from d3a_interface.constants_limits import ConstSettings
from tests.test_inter_area_agent import FakeMarket


class FakeArea:
    def __init__(self, name):
        self.name = name
        self.current_tick = 10
        self.transfer_fee_ratio = 0
        self.balancing_spot_trade_ratio = ConstSettings.BalancingSettings.SPOT_TRADE_RATIO
        self._fake_spot_market = FakeMarket([])

    def get_future_market_from_id(self, id):
        return self._fake_spot_market


class FakeBalancingMarket:
    def __init__(self, sorted_offers):
        self.id = 123
        self.sorted_offers = sorted_offers
        self.offers = {o.id: o for o in sorted_offers}
        self.forwarded_offer_id = 'fwd'
        self.area = FakeArea("fake_area")
        self.unmatched_energy_upward = 0
        self.unmatched_energy_downward = 0
        self._timeslot = pendulum.now(tz=TIME_ZONE)

    @property
    def time_slot(self):
        return self._timeslot

    def accept_offer(self, offer_or_id, buyer, energy=None, time=None,
                     trade_rate: float = None):
        if time is None:
            time = self.time_slot
        offer = offer_or_id
        if (offer.energy > 0 and energy < 0) or (offer.energy < 0 and energy > 0):
            raise InvalidBalancingTradeException("BalancingOffer and energy "
                                                 "are not compatible")

        if abs(energy) < abs(offer.energy):
            residual_energy = offer.energy - energy
            residual = BalancingOffer('res', pendulum.now(), offer.price, residual_energy,
                                      offer.seller)
            traded = BalancingOffer(offer.id, pendulum.now(), offer.price, energy, offer.seller)
            return BalancingTrade('trade_id', time, traded, traded.seller, buyer, residual)
        else:
            return BalancingTrade('trade_id', time, offer, offer.seller, buyer)


@pytest.fixture
def baa():
    lower_market = FakeBalancingMarket([BalancingOffer('id', pendulum.now(), 2, 2, 'other'),
                                        BalancingOffer('id', pendulum.now(), 2, -2, 'other')])
    higher_market = FakeBalancingMarket([])
    owner = FakeArea('owner')
    baa = BalancingAgent(owner=owner, lower_market=lower_market, higher_market=higher_market)
    return baa


def test_baa_event_trade(baa):
    trade = Trade('trade_id',
                  baa.lower_market.time_slot,
                  Offer('A', pendulum.now(), 2, 2, 'B'),
                  'someone_else',
                  'IAA owner')
    fake_spot_market = FakeMarket([])
    fake_spot_market.set_time_slot(baa.lower_market.time_slot)
    baa.event_trade(trade=trade,
                    market_id=fake_spot_market.id)
    assert baa.lower_market.unmatched_energy_upward == 0
    assert baa.lower_market.unmatched_energy_downward == 0


@pytest.fixture
def baa2():
    lower_market = FakeBalancingMarket([BalancingOffer('id', pendulum.now(), 2, 0.2, 'other'),
                                        BalancingOffer('id', pendulum.now(), 2, -0.2, 'other')])
    higher_market = FakeBalancingMarket([])
    owner = FakeArea('owner')
    baa = BalancingAgent(owner=owner, lower_market=lower_market, higher_market=higher_market)
    return baa


def test_baa_unmatched_event_trade(baa2):
    trade = Trade('trade_id',
                  pendulum.now(tz=TIME_ZONE),
                  Offer('A', pendulum.now(), 2, 2, 'B'),
                  'someone_else',
                  'IAA owner')
    fake_spot_market = FakeMarket([])
    fake_spot_market.set_time_slot(baa2.lower_market.time_slot)
    baa2.owner._fake_spot_market = fake_spot_market
    baa2.event_trade(trade=trade,
                     market_id=fake_spot_market.id)
    assert baa2.lower_market.unmatched_energy_upward != 0
    assert baa2.lower_market.unmatched_energy_downward != 0
