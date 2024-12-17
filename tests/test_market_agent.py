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

from copy import deepcopy
from math import isclose
from uuid import uuid4

import pendulum
import pytest

from gsy_framework.constants_limits import ConstSettings, GlobalConfig
from gsy_framework.data_classes import Bid, MarketClearingState, Offer, Trade, TraderDetails

from gsy_framework.constants_limits import TIME_FORMAT, TIME_ZONE
from gsy_e.models.market import GridFee
from gsy_e.models.market.grid_fees.base_model import GridFees
from gsy_e.models.strategy.market_agents.one_sided_agent import OneSidedAgent
from gsy_e.models.strategy.market_agents.settlement_agent import SettlementAgent
from gsy_e.models.strategy.market_agents.two_sided_agent import TwoSidedAgent
from gsy_e.models.strategy.market_agents.two_sided_engine import BidInfo


TRANSFER_FEES = GridFee(grid_fee_percentage=0, grid_fee_const=0)


class FakeArea:
    def __init__(self, name):
        self.name = name
        self.uuid = str(uuid4())
        self.current_tick = 10
        self.future_market = None
        self.now = pendulum.DateTime.now()
        self.transfer_fee_ratio = 0
        self.current_tick_in_slot = 0

    @property
    def config(self):
        return GlobalConfig

    def get_future_market_from_id(self, _id):
        return self.future_market


# pylint: disable=too-many-instance-attributes
class FakeMarket:
    # pylint: disable=too-many-arguments
    def __init__(self, offers, bids=None, m_id=123, transfer_fees=TRANSFER_FEES, name=None):
        self.name = name
        self.id = m_id
        self.offers = {o.id: o for o in offers}
        self._bids = bids if bids is not None else []
        self.bids = {bid.id: bid for bid in self._bids}
        self.offer_call_count = 0
        self.bid_call_count = 0
        self.forwarded_offer_id = "fwd"
        self.forwarded_bid_id = "fwd_bid_id"
        self.calls_energy = []
        self.calls_energy_bids = []
        self.calls_offers = []
        self.calls_bids = []
        self.calls_bids_price = []
        self.time_slot = pendulum.now(tz=TIME_ZONE)
        self.time_slot_str = self.time_slot.format(TIME_FORMAT)
        self.state = MarketClearingState()
        self.fee_class = GridFees(transfer_fees.grid_fee_percentage)

        self.forwarded_offer = None
        self.forwarded_bid = None

    @property
    def sorted_offers(self):
        return list(sorted(self.offers.values(), key=lambda b: b.energy_rate))

    def get_bids(self):
        return self.bids

    def set_time_slot(self, time_slot):
        self.time_slot = time_slot

    # pylint: disable=unused-argument
    def accept_offer(self, offer_or_id, buyer, *, energy=None, time=None, trade_bid_info=None):
        offer = offer_or_id
        self.calls_energy.append(energy)
        self.calls_offers.append(offer)
        if energy < offer.energy:
            residual_energy = offer.energy - energy
            residual = Offer(
                "res", offer.creation_time, offer.price, residual_energy, offer.seller
            )
            traded = Offer(offer.id, offer.creation_time, offer.price, energy, offer.seller)
            return Trade(
                "trade_id",
                time,
                traded.seller,
                TraderDetails(buyer, ""),
                residual=residual,
                offer=traded,
                traded_energy=1,
                trade_price=1,
            )

        return Trade(
            "trade_id",
            time,
            offer.seller,
            TraderDetails(buyer, ""),
            offer=offer,
            traded_energy=1,
            trade_price=1,
        )

    # pylint: disable=unused-argument
    # pylint: disable=too-many-locals
    def accept_bid(
        self, bid, energy, seller, buyer=None, *, time=None, trade_offer_info=None, offer=None
    ):
        self.calls_energy_bids.append(energy)
        self.calls_bids.append(bid)
        self.calls_bids_price.append(bid.price)
        if trade_offer_info is None:
            trade_rate = bid.energy_rate
        else:
            trade_rate = trade_offer_info.trade_rate

        assert trade_rate <= bid.energy_rate

        market_bid = [b for b in self._bids if b.id == bid.id][0]
        if energy < market_bid.energy:
            residual_energy = bid.energy - energy
            residual = Bid("res", bid.creation_time, bid.price, residual_energy, bid.buyer)
            traded = Bid(bid.id, bid.creation_time, (trade_rate * energy), energy, bid.buyer)
            return Trade(
                "trade_id",
                time,
                seller,
                bid.buyer,
                bid=traded,
                residual=residual,
                traded_energy=1,
                trade_price=1,
            )

        traded = Bid(bid.id, bid.creation_time, (trade_rate * energy), energy, bid.buyer)
        return Trade(
            "trade_id", time, seller, bid.buyer, bid=traded, traded_energy=1, trade_price=1
        )

    def delete_offer(self, *args):
        pass

    def delete_bid(self, *args):
        pass

    def _update_new_offer_price_with_fee(self, offer_price, original_price, energy):
        return offer_price + self.fee_class.grid_fee_rate * original_price

    def _update_new_bid_price_with_fee(self, bid_price, original_price):
        return self.fee_class.update_incoming_bid_with_fee(bid_price, original_price)

    def offer(
        self,
        price: float,
        energy: float,
        seller: TraderDetails,
        offer_id=None,
        original_price=None,
        dispatch_event=True,
        adapt_price_with_fees=True,
        time_slot=None,
    ) -> Offer:
        self.offer_call_count += 1

        if original_price is None:
            original_price = price
        if offer_id is None:
            offer_id = "uuid"
        if adapt_price_with_fees:
            price = self._update_new_offer_price_with_fee(price, original_price, energy)
        offer = Offer(offer_id, pendulum.now(), price, energy, seller, original_price)
        self.offers[offer.id] = deepcopy(offer)
        self.forwarded_offer = deepcopy(offer)

        return offer

    def dispatch_market_offer_event(self, offer):
        pass

    def dispatch_market_bid_event(self, bid):
        pass

    def bid(
        self,
        price: float,
        energy: float,
        buyer: TraderDetails,
        bid_id: str = None,
        original_price=None,
        dispatch_event=True,
        adapt_price_with_fees=True,
        time_slot=None,
    ):
        self.bid_call_count += 1

        if original_price is None:
            original_price = price

        if bid_id is None:
            bid_id = "uuid"

        if adapt_price_with_fees:
            price = self._update_new_bid_price_with_fee(price, original_price)

        bid = Bid(bid_id, pendulum.now(), price, energy, buyer, original_price=original_price)
        self._bids.append(bid)
        self.forwarded_bid = bid

        return bid

    def split_offer(self, original_offer, energy, orig_offer_price):
        self.offers.pop(original_offer.id, None)
        # same offer id is used for the new accepted_offer
        accepted_offer = self.offer(
            offer_id=original_offer.id,
            price=original_offer.price * (energy / original_offer.energy),
            energy=energy,
            seller=original_offer.seller,
            dispatch_event=False,
        )

        residual_price = (1 - energy / original_offer.energy) * original_offer.price
        residual_energy = original_offer.energy - energy
        original_residual_price = (
            (original_offer.energy - energy) / original_offer.energy
        ) * orig_offer_price

        residual_offer = self.offer(
            price=residual_price,
            energy=residual_energy,
            seller=original_offer.seller,
            original_price=original_residual_price,
            dispatch_event=False,
            adapt_price_with_fees=False,
        )

        return accepted_offer, residual_offer

    def split_bid(self, original_bid, energy, orig_bid_price):
        self.offers.pop(original_bid.id, None)
        # same offer id is used for the new accepted_offer
        accepted_bid = self.bid(
            bid_id=original_bid.id,
            buyer=original_bid.buyer,
            price=original_bid.price * (energy / original_bid.energy),
            energy=energy,
        )
        residual_price = (1 - energy / original_bid.energy) * original_bid.price
        residual_energy = original_bid.energy - energy
        original_residual_price = (
            (original_bid.energy - energy) / original_bid.energy
        ) * orig_bid_price

        residual_bid = self.bid(
            price=residual_price,
            buyer=original_bid.buyer,
            energy=residual_energy,
            original_price=original_residual_price,
            adapt_price_with_fees=False,
        )
        return accepted_bid, residual_bid


class TestMAGridFee:

    @staticmethod
    def teardown_method():
        ConstSettings.MASettings.MARKET_TYPE = 1
        ConstSettings.MASettings.PAY_AS_CLEAR_AGGREGATION_ALGORITHM = 1

    @staticmethod
    @pytest.fixture(name="market_agent")
    def market_agent_fixture():
        lower_market = FakeMarket(
            [Offer("id", pendulum.now(), 1, 1, TraderDetails("other", ""), 1)],
            transfer_fees=GridFee(grid_fee_percentage=0.1, grid_fee_const=2),
        )
        higher_market = FakeMarket(
            [
                Offer("id2", pendulum.now(), 3, 3, TraderDetails("owner", ""), 3),
                Offer("id3", pendulum.now(), 0.5, 1, TraderDetails("owner", ""), 0.5),
            ],
            transfer_fees=GridFee(grid_fee_percentage=0.1, grid_fee_const=2),
        )
        owner = FakeArea("owner")
        market_agent = OneSidedAgent(
            owner=owner, higher_market=higher_market, lower_market=lower_market
        )
        market_agent.event_tick()
        market_agent.owner.current_tick = 14
        market_agent.event_tick()

        return market_agent

    @staticmethod
    def test_ma_forwarded_offers_complied_to_transfer_fee(market_agent):
        source_offer = [
            offer for offer in market_agent.lower_market.sorted_offers if offer.id == "id"
        ][0]
        target_offer = [
            offer for offer in market_agent.higher_market.sorted_offers if offer.id == "uuid"
        ][0]
        earned_ma_fee = target_offer.price - source_offer.price
        expected_ma_fee = market_agent.higher_market.fee_class.grid_fee_rate

        assert isclose(earned_ma_fee, expected_ma_fee)

    @staticmethod
    @pytest.mark.parametrize("market_agent_fee", [0.1, 0, 0.5, 0.75, 0.05, 0.02, 0.03])
    def test_ma_forwards_bids_according_to_percentage(market_agent_fee):
        ConstSettings.MASettings.MARKET_TYPE = 2
        lower_market = FakeMarket(
            [],
            [Bid("id", pendulum.now(), 1, 1, TraderDetails("this", ""), 1)],
            transfer_fees=GridFee(grid_fee_percentage=market_agent_fee, grid_fee_const=0),
            name="FakeMarket",
        )
        higher_market = FakeMarket(
            [],
            [Bid("id2", pendulum.now(), 3, 3, TraderDetails("child", ""), 3)],
            transfer_fees=GridFee(grid_fee_percentage=market_agent_fee, grid_fee_const=0),
            name="FakeMarket",
        )
        market_agent = TwoSidedAgent(
            owner=FakeArea("owner"), higher_market=higher_market, lower_market=lower_market
        )
        market_agent.event_tick()
        market_agent.owner.current_tick = 14
        market_agent.event_tick()

        assert market_agent.higher_market.bid_call_count == 1
        assert market_agent.higher_market.forwarded_bid.price == list(
            market_agent.lower_market.bids.values()
        )[-1].price * (1 - market_agent_fee)

    @staticmethod
    @pytest.mark.parametrize("market_agent_fee_const", [0.5, 1, 5, 10])
    @pytest.mark.skip("need to define if we need a constant fee")
    def test_ma_forwards_bids_according_to_constantfee(market_agent_fee_const):
        ConstSettings.MASettings.MARKET_TYPE = 2
        lower_market = FakeMarket(
            [],
            [Bid("id", pendulum.now(), 15, 1, TraderDetails("this", ""), 15)],
            transfer_fees=GridFee(grid_fee_percentage=0, grid_fee_const=market_agent_fee_const),
        )
        higher_market = FakeMarket(
            [],
            [Bid("id2", pendulum.now(), 35, 3, TraderDetails("child", ""), 35)],
            transfer_fees=GridFee(grid_fee_percentage=0, grid_fee_const=market_agent_fee_const),
        )
        market_agent = TwoSidedAgent(
            owner=FakeArea("owner"), higher_market=higher_market, lower_market=lower_market
        )
        market_agent.event_tick()
        market_agent.owner.current_tick = 14
        market_agent.event_tick()

        assert market_agent.higher_market.bid_call_count == 1
        bid = list(market_agent.lower_market.bids.values())[-1]
        assert market_agent.higher_market.forwarded_bid.price == (
            bid.price - market_agent_fee_const * bid.energy
        )


@pytest.fixture(name="market_agent_bid", params=[TwoSidedAgent, SettlementAgent])
def market_agent_bid_fixture(request):
    ConstSettings.MASettings.MARKET_TYPE = 2
    lower_market = FakeMarket([], [Bid("id", pendulum.now(), 1, 1, TraderDetails("this", ""), 1)])
    higher_market = FakeMarket(
        [],
        [
            Bid("id2", pendulum.now(), 1, 1, TraderDetails("child", ""), 1),
            Bid("id3", pendulum.now(), 0.5, 1, TraderDetails("child", ""), 1),
        ],
    )
    owner = FakeArea("owner")

    agent_class = request.param
    market_agent = agent_class(owner=owner, higher_market=higher_market, lower_market=lower_market)
    market_agent.event_tick()
    market_agent.owner.current_tick = 14
    market_agent.event_tick()
    yield market_agent


@pytest.fixture(name="market_agent_double_sided")
def market_agent_double_sided_fixture():
    ConstSettings.MASettings.MARKET_TYPE = 2
    lower_market = FakeMarket(
        offers=[Offer("id", pendulum.now(), 2, 2, TraderDetails("other", ""), 2)],
        bids=[Bid("bid_id", pendulum.now(), 10, 10, TraderDetails("B", ""), 10)],
        transfer_fees=GridFee(grid_fee_percentage=0.01, grid_fee_const=0),
    )
    higher_market = FakeMarket(
        [], [], transfer_fees=GridFee(grid_fee_percentage=0.01, grid_fee_const=0)
    )
    owner = FakeArea("owner")
    market_agent = TwoSidedAgent(
        owner=owner, lower_market=lower_market, higher_market=higher_market
    )
    market_agent.event_tick()
    market_agent.owner.current_tick += 2
    market_agent.event_tick()
    yield market_agent


# pylint: disable=protected-access
class TestMABid:

    @staticmethod
    def teardown_method():
        ConstSettings.MASettings.MARKET_TYPE = 1
        ConstSettings.MASettings.PAY_AS_CLEAR_AGGREGATION_ALGORITHM = 1

    @staticmethod
    def test_ma_forwards_bids(market_agent_bid):
        assert market_agent_bid.lower_market.bid_call_count == 2
        assert market_agent_bid.higher_market.bid_call_count == 1

    @staticmethod
    def test_ma_forwarded_bids_adhere_to_ma_overhead(market_agent_bid):
        assert market_agent_bid.higher_market.bid_call_count == 1
        expected_price = list(market_agent_bid.lower_market.bids.values())[-1].price * (
            1 - market_agent_bid.lower_market.fee_class.grid_fee_rate
        )
        assert market_agent_bid.higher_market.forwarded_bid.price == expected_price

    @staticmethod
    def test_ma_event_trade_bid_deletes_forwarded_bid_when_sold(market_agent_bid, called):
        market_agent_bid.lower_market.delete_bid = called
        market_agent_bid.event_bid_traded(
            bid_trade=Trade(
                "trade_id",
                pendulum.now(tz=TIME_ZONE),
                TraderDetails("someone_else", ""),
                TraderDetails("owner", ""),
                bid=market_agent_bid.higher_market.bids["id3"],
                traded_energy=1,
                trade_price=1,
            ),
            market_id=market_agent_bid.higher_market.id,
        )
        assert len(market_agent_bid.lower_market.delete_bid.calls) == 1

    @staticmethod
    def test_ma_event_trade_bid_does_not_delete_forwarded_bid_of_counterpart(
        market_agent_bid, called
    ):
        market_agent_bid.lower_market.delete_bid = called
        high_to_low_engine = market_agent_bid.engines[1]
        high_to_low_engine.event_bid_traded(
            bid_trade=Trade(
                "trade_id",
                pendulum.now(tz=TIME_ZONE),
                bid=market_agent_bid.higher_market.bids["id3"],
                seller=TraderDetails("owner", ""),
                buyer=TraderDetails("someone_else", ""),
                traded_energy=1,
                trade_price=1,
            )
        )
        assert len(market_agent_bid.lower_market.delete_bid.calls) == 0

    @staticmethod
    @pytest.mark.parametrize("partial", [True, False])
    def test_ma_event_bid_split_and_trade_correctly_populate_forwarded_bid_entries(
        market_agent_bid, called, partial
    ):
        market_agent_bid.lower_market.delete_bid = called
        low_to_high_engine = market_agent_bid.engines[0]
        market_agent_bid._get_market_from_market_id = lambda x: low_to_high_engine.markets.target

        source_bid = list(low_to_high_engine.markets.source.bids.values())[0]
        target_bid = list(low_to_high_engine.markets.target.bids.values())[0]
        bidinfo = BidInfo(source_bid=source_bid, target_bid=target_bid)
        low_to_high_engine.forwarded_bids[source_bid.id] = bidinfo
        low_to_high_engine.forwarded_bids[target_bid.id] = bidinfo

        if partial:
            residual_energy = 0.2
            residual_id = "resid"
            original_bid = low_to_high_engine.markets.target._bids[0]

            accepted_bid = deepcopy(original_bid)
            accepted_bid.update_price(
                (original_bid.energy - residual_energy) * (original_bid.energy_rate)
            )
            accepted_bid.update_energy(original_bid.energy - residual_energy)

            residual_bid = deepcopy(original_bid)
            residual_bid.id = residual_id
            residual_bid.update_price(residual_energy * original_bid.energy_rate)
            residual_bid.update_energy(residual_energy)

            low_to_high_engine.event_bid_split(
                market_id=low_to_high_engine.markets.target.id,
                original_bid=original_bid,
                accepted_bid=accepted_bid,
                residual_bid=residual_bid,
            )
            assert set(low_to_high_engine.forwarded_bids.keys()) == {
                original_bid.id,
                accepted_bid.id,
                residual_bid.id,
                "uuid",
                "id3",
                "id2",
            }
        else:
            original_bid = low_to_high_engine.markets.target._bids[0]
            accepted_bid = deepcopy(original_bid)
            residual_bid = None

        low_to_high_engine.event_bid_traded(
            bid_trade=Trade(
                "trade_id",
                pendulum.now(tz=TIME_ZONE),
                bid=accepted_bid,
                seller=TraderDetails("someone_else", ""),
                buyer=TraderDetails("owner", ""),
                residual=residual_bid,
                traded_energy=1,
                trade_price=1,
            )
        )

        if partial:
            # "id" gets traded in the target market, "id2" gets split in the source market, too
            assert set(low_to_high_engine.forwarded_bids.keys()) == {
                residual_bid.id,
                "uuid",
                "id3",
            }
        else:
            # "id" and "id2" get traded in both target and source,
            # left over is id3 and its forwarded instance uuid
            assert set(low_to_high_engine.forwarded_bids.keys()) == {"uuid", "id3"}

    @staticmethod
    def test_ma_event_trade_buys_accepted_bid(market_agent_double_sided):
        market_agent_double_sided.higher_market.forwarded_bid = (
            market_agent_double_sided.higher_market.forwarded_bid
        )
        market_agent_double_sided.event_bid_traded(
            bid_trade=Trade(
                "trade_id",
                pendulum.now(tz=TIME_ZONE),
                TraderDetails("owner", ""),
                TraderDetails("someone_else", ""),
                bid=market_agent_double_sided.higher_market.forwarded_bid,
                traded_energy=1,
                trade_price=1,
            ),
            market_id=market_agent_double_sided.higher_market.id,
        )
        assert len(market_agent_double_sided.lower_market.calls_energy_bids) == 1

        expected_price = 10 * (1 - market_agent_double_sided.lower_market.fee_class.grid_fee_rate)
        assert market_agent_double_sided.higher_market.forwarded_bid.price == expected_price
        assert market_agent_double_sided.lower_market.calls_bids_price[-1] == 10.0

    @staticmethod
    def test_ma_event_bid_trade_increases_bid_price(market_agent_double_sided):
        market_agent_double_sided.event_bid_traded(
            bid_trade=Trade(
                "trade_id",
                pendulum.now(tz=TIME_ZONE),
                TraderDetails("owner", ""),
                TraderDetails("someone_else", ""),
                bid=market_agent_double_sided.higher_market.forwarded_bid,
                traded_energy=1,
                trade_price=1,
            ),
            market_id=market_agent_double_sided.higher_market.id,
        )
        assert len(market_agent_double_sided.lower_market.calls_energy_bids) == 1
        expected_price = 10 * (1 - market_agent_double_sided.lower_market.fee_class.grid_fee_rate)
        assert market_agent_double_sided.higher_market.forwarded_bid.price == expected_price

        assert market_agent_double_sided.lower_market.calls_bids_price[-1] == 10

    @staticmethod
    def test_ma_event_trade_buys_partial_accepted_bid(market_agent_double_sided):
        market_agent_double_sided._get_market_from_market_id = (
            lambda x: market_agent_double_sided.higher_market
        )
        original_bid = market_agent_double_sided.higher_market.forwarded_bid
        accepted_bid_price = (original_bid.price / original_bid.energy) * 1
        residual_bid_price = (original_bid.price / original_bid.energy) * 0.1
        accepted_bid = Bid(
            original_bid.id, original_bid.creation_time, accepted_bid_price, 1, original_bid.buyer
        )
        residual_bid = Bid(
            "residual_bid", original_bid.creation_time, residual_bid_price, 0.1, original_bid.buyer
        )
        market_agent_double_sided.event_bid_split(
            market_id=market_agent_double_sided.higher_market.id,
            original_bid=original_bid,
            accepted_bid=accepted_bid,
            residual_bid=residual_bid,
        )
        market_agent_double_sided.event_bid_traded(
            bid_trade=Trade(
                "trade_id",
                pendulum.now(tz=TIME_ZONE),
                TraderDetails("owner", ""),
                TraderDetails("someone_else", ""),
                bid=accepted_bid,
                residual="residual_offer",
                traded_energy=1,
                trade_price=1,
            ),
            market_id=market_agent_double_sided.higher_market.id,
        )
        assert market_agent_double_sided.lower_market.calls_energy_bids[0] == 1

    @staticmethod
    def test_ma_forwards_partial_bid_from_source_market(market_agent_double_sided):
        market_agent_double_sided._get_market_from_market_id = (
            lambda x: market_agent_double_sided.lower_market
        )
        original_bid = market_agent_double_sided.lower_market._bids[0]
        residual_energy = 0.1
        accepted_bid = Bid(
            original_bid.id,
            original_bid.creation_time,
            original_bid.price,
            original_bid.energy - residual_energy,
            original_bid.buyer,
            original_bid.price,
        )
        residual_bid = Bid(
            "residual_bid",
            original_bid.creation_time,
            original_bid.price,
            residual_energy,
            original_bid.buyer,
            original_bid.price,
        )
        market_agent_double_sided.usable_bid = lambda s: True
        market_agent_double_sided.event_bid_split(
            market_id=market_agent_double_sided.lower_market.id,
            original_bid=original_bid,
            accepted_bid=accepted_bid,
            residual_bid=residual_bid,
        )
        assert isclose(
            market_agent_double_sided.higher_market.forwarded_bid.energy, residual_energy
        )


class TestMAOffer:

    @staticmethod
    def teardown_method():
        ConstSettings.MASettings.MARKET_TYPE = 1
        ConstSettings.MASettings.PAY_AS_CLEAR_AGGREGATION_ALGORITHM = 1

    @staticmethod
    @pytest.fixture(name="market_agent")
    def market_agent_fixture():
        lower_market = FakeMarket(
            [Offer("id", pendulum.now(), 1, 1, TraderDetails("other", ""), 1)]
        )
        higher_market = FakeMarket(
            [
                Offer("id2", pendulum.now(), 3, 3, TraderDetails("higher", ""), 3),
                Offer("id3", pendulum.now(), 0.5, 1, TraderDetails("higher", ""), 0.5),
            ]
        )
        owner = FakeArea("owner")
        maa = OneSidedAgent(owner=owner, higher_market=higher_market, lower_market=lower_market)
        maa.event_tick()
        maa.owner.current_tick = 14
        maa.event_tick()

        return maa

    @staticmethod
    @pytest.fixture(name="market_agent_2")
    def market_agent_2_fixture():
        lower_market = FakeMarket(
            [Offer("id", pendulum.now(), 2, 2, TraderDetails("other", ""), 2)], m_id=123
        )
        higher_market = FakeMarket([], m_id=234)
        owner = FakeArea("owner")
        owner.future_market = lower_market
        maa = OneSidedAgent(owner=owner, lower_market=lower_market, higher_market=higher_market)
        maa.event_tick()
        maa.owner.current_tick += 2
        maa.event_tick()

        return maa

    @staticmethod
    def test_ma_forwards_offers(market_agent):
        assert market_agent.lower_market.offer_call_count == 2
        assert market_agent.higher_market.offer_call_count == 1

    @staticmethod
    def test_ma_event_trade_deletes_forwarded_offer_when_sold(market_agent, called):
        market_agent.lower_market.delete_offer = called
        market_agent.event_offer_traded(
            trade=Trade(
                "trade_id",
                pendulum.now(tz=TIME_ZONE),
                TraderDetails("higher", ""),
                TraderDetails("someone_else", ""),
                offer=market_agent.higher_market.offers["id3"],
                traded_energy=1,
                trade_price=1,
            ),
            market_id=market_agent.higher_market.id,
        )
        assert len(market_agent.lower_market.delete_offer.calls) == 1

    @staticmethod
    def test_ma_event_trade_buys_accepted_offer(market_agent_2):
        market_agent_2.event_offer_traded(
            trade=Trade(
                "trade_id",
                pendulum.now(tz=TIME_ZONE),
                TraderDetails("owner", ""),
                TraderDetails("someone_else", ""),
                offer=market_agent_2.higher_market.forwarded_offer,
                fee_price=0.0,
                traded_energy=1,
                trade_price=1,
            ),
            market_id=market_agent_2.higher_market.id,
        )
        assert len(market_agent_2.lower_market.calls_energy) == 1

    @staticmethod
    def test_ma_event_trade_buys_partial_accepted_offer(market_agent_2):
        total_offer = market_agent_2.higher_market.forwarded_offer
        accepted_offer = Offer(
            total_offer.id, total_offer.creation_time, total_offer.price, 1, total_offer.seller
        )
        market_agent_2.event_offer_traded(
            trade=Trade(
                "trade_id",
                pendulum.now(tz=TIME_ZONE),
                TraderDetails("owner", ""),
                TraderDetails("someone_else", ""),
                offer=accepted_offer,
                traded_energy=1,
                trade_price=1,
                residual="residual_offer",
                fee_price=0.0,
            ),
            market_id=market_agent_2.higher_market.id,
        )
        assert market_agent_2.lower_market.calls_energy[0] == 1

    @staticmethod
    def test_ma_event_offer_split_and_trade_correctly_populate_forwarded_offer_entries(
        market_agent_2,
    ):
        residual_offer_id = "res_id"
        original_offer_id = "id"
        original = market_agent_2.higher_market.forwarded_offer
        assert original.energy == 2

        accepted = Offer(original.id, pendulum.now(), 1, 1, original.seller)
        residual = Offer(residual_offer_id, pendulum.now(), 1, 1, original.seller)

        market_agent_2.event_offer_split(
            market_id=market_agent_2.higher_market.id,
            original_offer=original,
            accepted_offer=accepted,
            residual_offer=residual,
        )
        engine = next(
            (e for e in market_agent_2.engines if residual_offer_id in e.forwarded_offers), None
        )
        assert engine is not None, "Residual of forwarded offers not found in forwarded_offers"

        # after the split event:
        # all three offer ids are part of the forwarded_offer member
        assert set(engine.forwarded_offers.keys()) == {
            residual_offer_id,
            original_offer_id,
            "uuid",
        }
        # and the accepted offer was added
        assert engine.forwarded_offers[original_offer_id].target_offer.energy == accepted.energy
        # and the residual offer was added
        assert engine.forwarded_offers[residual_offer_id].target_offer.energy == accepted.energy

        market_agent_2.event_offer_traded(
            trade=Trade(
                "trade_id",
                pendulum.now(tz=TIME_ZONE),
                TraderDetails("owner", ""),
                TraderDetails("someone_else", ""),
                offer=accepted,
                traded_energy=1,
                trade_price=1,
                residual=residual,
                fee_price=0.0,
            ),
            market_id=market_agent_2.lower_market.id,
        )

        # after the trade event:
        # the forwarded_offers only contain the residual offer
        assert set(engine.forwarded_offers.keys()) == {residual_offer_id}
        offer_info = engine.forwarded_offers[residual_offer_id]
        assert offer_info.source_offer.id == "uuid"
        assert offer_info.target_offer.id == residual_offer_id
