"""
Copyright 2018 Grid Singularity
This file is part of Grid Singularity Exchange.

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

# pylint: disable=missing-class-docstring
# pylint: disable=missing-function-docstring

from uuid import uuid4

import pendulum
import pytest

from gsy_framework.constants_limits import ConstSettings
from gsy_framework.data_classes import BalancingOffer, BalancingTrade, Offer, Trade, TraderDetails

from gsy_framework.constants_limits import TIME_ZONE
from gsy_e.gsy_e_core.exceptions import InvalidBalancingTradeException
from gsy_e.models.strategy.market_agents.balancing_agent import BalancingAgent
from tests.test_market_agent import FakeMarket


class FakeArea:
    def __init__(self, name):
        self.name = name
        self.uuid = str(uuid4())
        self.current_tick = 10
        self.transfer_fee_ratio = 0
        self.balancing_spot_trade_ratio = ConstSettings.BalancingSettings.SPOT_TRADE_RATIO

        self.fake_spot_market = FakeMarket([])

    def get_future_market_from_id(self, _id):
        return self.fake_spot_market


class FakeBalancingMarket:
    def __init__(self, sorted_offers):
        self.id = 123
        self.sorted_offers = sorted_offers
        self.offers = {o.id: o for o in sorted_offers}
        self.area = FakeArea("fake_area")
        self.unmatched_energy_upward = 0
        self.unmatched_energy_downward = 0
        self._time_slot = pendulum.now(tz=TIME_ZONE)

    @property
    def time_slot(self):
        return self._time_slot

    # pylint: disable=unused-argument
    # pylint: disable=too-many-arguments
    def accept_offer(self, offer_or_id, buyer, energy=None, time=None, trade_rate: float = None):
        if time is None:
            time = self.time_slot
        offer = offer_or_id
        if (energy < 0 < offer.energy) or (offer.energy < 0 < energy):
            raise InvalidBalancingTradeException("BalancingOffer and energy are not compatible")

        if abs(energy) < abs(offer.energy):
            residual_energy = offer.energy - energy
            residual = BalancingOffer(
                "res", pendulum.now(), offer.price, residual_energy, offer.seller
            )
            traded = BalancingOffer(offer.id, pendulum.now(), offer.price, energy, offer.seller)
            return BalancingTrade(
                "trade_id",
                time,
                traded.seller,
                buyer,
                residual=residual,
                offer=traded,
                traded_energy=1,
                trade_price=1,
            )

        return BalancingTrade(
            "trade_id", time, offer.seller, buyer, offer=offer, traded_energy=1, trade_price=1
        )


@pytest.fixture(name="balancing_agent")
def balancing_agent_fixture():
    lower_market = FakeBalancingMarket(
        [
            BalancingOffer("id", pendulum.now(), 2, 2, TraderDetails("other", "")),
            BalancingOffer("id", pendulum.now(), 2, -2, TraderDetails("other", "")),
        ]
    )
    higher_market = FakeBalancingMarket([])
    owner = FakeArea("owner")
    baa = BalancingAgent(owner=owner, lower_market=lower_market, higher_market=higher_market)
    return baa


def test_baa_event_trade(balancing_agent):
    trade = Trade(
        "trade_id",
        balancing_agent.lower_market.time_slot,
        TraderDetails("someone_else", ""),
        TraderDetails("MA owner", ""),
        offer=Offer("A", pendulum.now(), 2, 2, TraderDetails("B", "")),
        traded_energy=1,
        trade_price=1,
    )
    fake_spot_market = FakeMarket([])
    fake_spot_market.set_time_slot(balancing_agent.lower_market.time_slot)
    balancing_agent.event_offer_traded(trade=trade, market_id=fake_spot_market.id)

    assert balancing_agent.lower_market.unmatched_energy_upward == 0
    assert balancing_agent.lower_market.unmatched_energy_downward == 0


@pytest.fixture(name="balancing_agent_2")
def balancing_agent_2_fixture():
    lower_market = FakeBalancingMarket(
        [
            BalancingOffer("id", pendulum.now(), 2, 0.2, TraderDetails("other", "")),
            BalancingOffer("id", pendulum.now(), 2, -0.2, TraderDetails("other", "")),
        ]
    )
    higher_market = FakeBalancingMarket([])
    owner = FakeArea("owner")
    baa = BalancingAgent(owner=owner, lower_market=lower_market, higher_market=higher_market)

    return baa


def test_baa_unmatched_event_trade(balancing_agent_2):
    trade = Trade(
        "trade_id",
        pendulum.now(tz=TIME_ZONE),
        TraderDetails("someone_else", ""),
        TraderDetails("owner", ""),
        offer=Offer("A", pendulum.now(), 2, 2, TraderDetails("B", "")),
        traded_energy=1,
        trade_price=1,
    )
    fake_spot_market = FakeMarket([])
    fake_spot_market.set_time_slot(balancing_agent_2.lower_market.time_slot)
    balancing_agent_2.owner.fake_spot_market = fake_spot_market
    balancing_agent_2.event_offer_traded(trade=trade, market_id=fake_spot_market.id)

    assert balancing_agent_2.lower_market.unmatched_energy_upward != 0
    assert balancing_agent_2.lower_market.unmatched_energy_downward != 0
