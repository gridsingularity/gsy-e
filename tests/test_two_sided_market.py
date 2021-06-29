from math import isclose
from unittest.mock import MagicMock

import pytest
from d3a.d3a_core.exceptions import (
    BidNotFoundException, InvalidBid, InvalidBidOfferPair, InvalidTrade)
from d3a.events import MarketEvent
from d3a.models.market import Bid, Offer
from d3a.models.market.market_structures import TradeBidOfferInfo
from d3a.models.market.two_sided import TwoSidedMarket
from d3a.models.myco_matcher import PayAsBidMatcher, PayAsClearMatcher
from d3a_interface.constants_limits import ConstSettings
from pendulum import now


@pytest.fixture
def market():
    return TwoSidedMarket(time_slot=now())


@pytest.fixture
def pac_market():
    return PayAsClearMatcher()


@pytest.fixture
def market_matcher():
    return PayAsBidMatcher()


class TestTwoSidedMarket:
    """Class Responsible for testing two sided market"s functionality."""

    def test_double_sided_validate_requirements_satisfied(self, market):
        offer = Offer("id", now(), 2, 2, "other", 2,
                      requirements=[{"preferred_trading_partners": ["bid_id2"]}],
                      attributes={"energy_type": "Green"})
        bid = Bid("bid_id", now(), 9, 10, "B", 9,
                  buyer_id="bid_id", requirements=[], attributes={})
        with pytest.raises(InvalidBidOfferPair):
            # should raise an exception as buyer_id is not in preferred_trading_partners
            market.validate_requirements_satisfied(offer, bid)
        bid.buyer_id = "bid_id2"
        market.validate_requirements_satisfied(offer, bid)  # Should not raise any exceptions
        bid.requirements.append({"energy_type": ["Grey"]})
        with pytest.raises(InvalidBidOfferPair):
            # should raise an exception as energy_type of offer needs to be in [Grey, ]
            market.validate_requirements_satisfied(offer, bid)

        # Adding another requirement that is satisfied, should not raise an exception
        bid.requirements.append({"energy_type": ["Green"]})
        market.validate_requirements_satisfied(offer, bid)

        offer.requirements.append({"hashed_identity": "AreaX"})
        # Above is an unsatisfied requirement but it will pass anw as
        # there are other satisfied requirement
        market.validate_requirements_satisfied(offer, bid)
        bid.requirements = [{"hashed_identity": "AreaX"}]
        with pytest.raises(InvalidBidOfferPair):
            # should raise an exception as hashed_identity requirement of offer isn"t satisfied
            market.validate_requirements_satisfied(offer, bid)
        offer.attributes["hashed_identity"] = "AreaX"
        market.validate_requirements_satisfied(offer, bid)

    @pytest.mark.parametrize(
        "bid_energy, offer_energy, clearing_rate, selected_energy", [
            (2, 3, 2, 2.5),
            (3, 2, 2, 2.5),
            (2, 2, 2 / 2 + 1, 2),
            (2, 2.5, 2, 2),
        ])
    def test_validate_authentic_bid_offer_pair_raises_exception(
            self, market, bid_energy, offer_energy, clearing_rate, selected_energy):
        offer = Offer("id", now(), 2, offer_energy, "other", 2)
        bid = Bid("bid_id", now(), 2, bid_energy, "B", 8)
        TwoSidedMarket.validate_requirements_satisfied = MagicMock()
        with pytest.raises(InvalidBidOfferPair):
            market.validate_authentic_bid_offer_pair(bid, offer, clearing_rate, selected_energy)
            TwoSidedMarket.validate_requirements_satisfied.assert_not_called()

    def test_double_sided_performs_pay_as_bid_matching(
            self, market: TwoSidedMarket, market_matcher):
        market.offers = {"offer1": Offer("id", now(), 2, 2, "other", 2)}

        market.bids = {"bid1": Bid("bid_id", now(), 9, 10, "B", "S")}
        matched = list(market_matcher.calculate_match_recommendation(
            market.bids, market.offers))
        assert len(matched) == 0
        market.bids = {"bid1": Bid("bid_id", now(), 11, 10, "B", "S")}
        matched = list(market_matcher.calculate_match_recommendation(
            market.bids, market.offers))
        assert len(matched) == 1

        assert matched[0].bid == list(market.bids.values())[0]
        assert matched[0].offer == list(market.offers.values())[0]

        market.bids = {"bid1": Bid("bid_id1", now(), 11, 10, "B", "S"),
                       "bid2": Bid("bid_id2", now(), 9, 10, "B", "S"),
                       "bid3": Bid("bid_id3", now(), 12, 10, "B", "S")}
        matched = list(market_matcher.calculate_match_recommendation(
            market.bids, market.offers))
        assert len(matched) == 1
        assert matched[0].bid.id == "bid_id3"
        assert matched[0].bid.price == 12
        assert matched[0].bid.energy == 10
        assert matched[0].offer == list(market.offers.values())[0]

    def test_market_bid(self, market: TwoSidedMarket):
        bid = market.bid(1, 2, "bidder", "bidder")
        assert market.bids[bid.id] == bid
        assert bid.price == 1
        assert bid.energy == 2
        assert bid.buyer == "bidder"
        assert len(bid.id) == 36

    def test_market_bid_accepts_bid_id(self, market: TwoSidedMarket):
        bid = market.bid(1, 2, "bidder", "bidder", bid_id="123")
        assert market.bids["123"] == bid
        assert bid.id == "123"
        assert bid.price == 1
        assert bid.energy == 2
        assert bid.buyer == "bidder"

        # Update existing bid is tested here
        bid = market.bid(3, 4, "updated_bidder", "updated_bidder", bid_id="123")
        assert market.bids["123"] == bid
        assert bid.id == "123"
        assert isclose(bid.price, 3)
        assert bid.energy == 4
        assert bid.buyer == "updated_bidder"

    def test_market_bid_invalid(self, market: TwoSidedMarket):
        with pytest.raises(InvalidBid):
            market.bid(10, -1, "someone", "someone")

    def test_market_bid_delete(self, market: TwoSidedMarket):
        bid = market.bid(20, 10, "someone", "someone")
        assert bid.id in market.bids

        market.delete_bid(bid)
        assert bid.id not in market.bids

    def test_market_bid_delete_id(self, market: TwoSidedMarket):
        bid = market.bid(20, 10, "someone", "someone")
        assert bid.id in market.bids

        market.delete_bid(bid.id)
        assert bid.id not in market.bids

    def test_market_bid_delete_missing(self, market: TwoSidedMarket):
        with pytest.raises(BidNotFoundException):
            market.delete_bid("no such offer")

    def test_double_sided_pay_as_clear_market_works_with_floats(self, pac_market):
        ConstSettings.IAASettings.PAY_AS_CLEAR_AGGREGATION_ALGORITHM = 1
        pac_market.offers = {"offer1": Offer("id1", now(), 1.1, 1, "other"),
                             "offer2": Offer("id2", now(), 2.2, 1, "other"),
                             "offer3": Offer("id3", now(), 3.3, 1, "other")}

        pac_market.bids = {
            "bid1": Bid("bid_id1", now(), 3.3, 1, "B", "S"),
            "bid2": Bid("bid_id2", now(), 2.2, 1, "B", "S"),
            "bid3": Bid("bid_id3", now(), 1.1, 1, "B", "S")}

        matched = pac_market.get_clearing_point(pac_market.bids, pac_market.offers, now())[0]
        assert matched == 2.2

    def test_market_bid_trade(self, market=TwoSidedMarket(bc=MagicMock(), time_slot=now())):
        bid = market.bid(20, 10, "A", "A", original_bid_price=20)
        trade_offer_info = TradeBidOfferInfo(2, 2, 0.5, 0.5, 2)
        trade = market.accept_bid(bid, energy=10, seller="B", trade_offer_info=trade_offer_info)
        assert trade
        assert trade.id == market.trades[0].id
        assert trade.id
        assert trade.offer.price == bid.price
        assert trade.offer.energy == bid.energy
        assert trade.seller == "B"
        assert trade.buyer == "A"
        assert not trade.residual

    def test_market_trade_bid_not_found(
            self, market=TwoSidedMarket(bc=MagicMock(), time_slot=now())):
        bid = market.bid(20, 10, "A", "A")
        trade_offer_info = TradeBidOfferInfo(2, 2, 1, 1, 2)
        assert market.accept_bid(bid, 10, "B", trade_offer_info=trade_offer_info)

        with pytest.raises(BidNotFoundException):
            market.accept_bid(bid, 10, "B", trade_offer_info=trade_offer_info)

    def test_market_trade_bid_partial(
            self, market=TwoSidedMarket(bc=MagicMock(), time_slot=now())):
        bid = market.bid(20, 20, "A", "A", original_bid_price=20)
        trade_offer_info = TradeBidOfferInfo(1, 1, 1, 1, 1)
        trade = market.accept_bid(bid, energy=5, seller="B", trade_offer_info=trade_offer_info)
        assert trade
        assert trade.id == market.trades[0].id
        assert trade.id
        assert trade.offer is not bid
        assert trade.offer.energy == 5
        assert trade.offer.price == 5
        assert trade.seller == "B"
        assert trade.buyer == "A"
        assert trade.residual
        assert len(market.bids) == 1
        assert trade.residual.id in market.bids
        assert market.bids[trade.residual.id].energy == 15
        assert isclose(market.bids[trade.residual.id].price, 15)
        assert market.bids[trade.residual.id].buyer == "A"

    def test_market_accept_bid_emits_bid_split_on_partial_bid(
            self, called, market=TwoSidedMarket(bc=MagicMock(), time_slot=now())):
        market.add_listener(called)
        bid = market.bid(20, 20, "A", "A")
        trade_offer_info = TradeBidOfferInfo(1, 1, 1, 1, 1)
        trade = market.accept_bid(bid, energy=1, trade_offer_info=trade_offer_info)
        assert all([ev != repr(MarketEvent.BID_DELETED) for c in called.calls for ev in c[0]])
        assert len(called.calls) == 2
        assert called.calls[0][0] == (repr(MarketEvent.BID_SPLIT),)
        assert called.calls[1][0] == (repr(MarketEvent.BID_TRADED),)
        assert called.calls[1][1] == {
            "market_id": repr(market.id),
            "bid_trade": repr(trade),
        }

    @pytest.mark.parametrize("market_method", ("_update_accumulated_trade_price_energy",
                                               "_update_min_max_avg_trade_prices"))
    def test_market_accept_bid_always_updates_trade_stats(
            self, called, market_method, market=TwoSidedMarket(bc=MagicMock(), time_slot=now())):
        setattr(market, market_method, called)

        bid = market.bid(20, 20, "A", "A")
        trade_offer_info = TradeBidOfferInfo(1, 1, 1, 1, 1)
        trade = market.accept_bid(bid, energy=5, seller="B", trade_offer_info=trade_offer_info)
        assert trade
        assert len(getattr(market, market_method).calls) == 1

    @pytest.mark.parametrize("energy", (0, 21, 100, -20))
    def test_market_trade_partial_bid_invalid(
            self, energy, market=TwoSidedMarket(bc=MagicMock(), time_slot=now())):
        bid = market.bid(20, 20, "A", "A")
        trade_offer_info = TradeBidOfferInfo(1, 1, 1, 1, 1)
        with pytest.raises(InvalidTrade):
            market.accept_bid(bid, energy=energy, seller="A", trade_offer_info=trade_offer_info)

    def test_market_accept_bid_yields_partial_bid_trade(
            self, market=TwoSidedMarket(bc=MagicMock(), time_slot=now())):
        bid = market.bid(2.0, 4, "buyer", "buyer")
        trade_offer_info = TradeBidOfferInfo(2, 2, 1, 1, 2)
        trade = market.accept_bid(bid, energy=1, seller="seller",
                                  trade_offer_info=trade_offer_info)
        assert trade.offer.id == bid.id and trade.offer.energy == 1

    @pytest.mark.parametrize("offer, bid, mcp_rate, mcp_energy", [
        ([1, 2, 3, 4, 5, 6, 7], [1, 2, 3, 4, 5, 6, 7], 4, 4),
        ([1, 2, 3, 4, 5, 6, 7], [7, 6, 5, 4, 3, 2, 1], 4, 4),
        ([8, 9, 10, 11, 12, 13, 14], [8, 9, 10, 11, 12, 13, 14], 11, 4),
        ([2, 3, 3, 5, 6, 7, 8], [1, 2, 3, 4, 5, 6, 7], 5, 3),
        ([10, 10, 10, 10, 10, 10, 10], [1, 2, 3, 4, 10, 10, 10], 10, 3),
        ([1, 2, 5, 5, 5, 6, 7], [5, 5, 5, 5, 5, 5, 5], 5, 5),
        # TODO: Future enhancement story to decide multiple offers
        #  acceptance/rejection having energy_rate equals to clearing_rate
        # ([2, 3, 6, 7, 7, 7, 7], [7, 5, 5, 2, 2, 2, 2], 5, 2),
        # ([2, 2, 4, 4, 4, 4, 6], [6, 6, 6, 6, 2, 2, 2], 4, 4),
    ])
    @pytest.mark.parametrize("algorithm", [1])
    def test_double_sided_market_performs_pay_as_clear_matching(
            self, pac_market, offer, bid, mcp_rate, mcp_energy, algorithm):
        ConstSettings.IAASettings.PAY_AS_CLEAR_AGGREGATION_ALGORITHM = algorithm
        pac_market.offers = {"offer1": Offer("id1", now(), offer[0], 1, "other"),
                             "offer2": Offer("id2", now(), offer[1], 1, "other"),
                             "offer3": Offer("id3", now(), offer[2], 1, "other"),
                             "offer4": Offer("id4", now(), offer[3], 1, "other"),
                             "offer5": Offer("id5", now(), offer[4], 1, "other"),
                             "offer6": Offer("id6", now(), offer[5], 1, "other"),
                             "offer7": Offer("id7", now(), offer[6], 1, "other")}

        pac_market.bids = {"bid1": Bid("bid_id1", now(), bid[0], 1, "B", "S"),
                           "bid2": Bid("bid_id2", now(), bid[1], 1, "B", "S"),
                           "bid3": Bid("bid_id3", now(), bid[2], 1, "B", "S"),
                           "bid4": Bid("bid_id4", now(), bid[3], 1, "B", "S"),
                           "bid5": Bid("bid_id5", now(), bid[4], 1, "B", "S"),
                           "bid6": Bid("bid_id6", now(), bid[5], 1, "B", "S"),
                           "bid7": Bid("bid_id7", now(), bid[6], 1, "B", "S")}

        matched_rate, matched_energy = pac_market.get_clearing_point(
            pac_market.bids, pac_market.offers, now()
        )
        assert matched_rate == mcp_rate
        assert matched_energy == mcp_energy
