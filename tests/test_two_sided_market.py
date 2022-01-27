# pylint: disable=missing-function-docstring, protected-access, too-many-public-methods, fixme
from math import isclose
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pendulum
import pytest
from gsy_framework.constants_limits import ConstSettings
from gsy_framework.data_classes import BidOfferMatch
from gsy_framework.data_classes import TradeBidOfferInfo, Trade
from gsy_framework.matching_algorithms import (
    PayAsBidMatchingAlgorithm, PayAsClearMatchingAlgorithm
)
from pendulum import now

from gsy_e.gsy_e_core.blockchain_interface import NonBlockchainInterface
from gsy_e.gsy_e_core.exceptions import (
    BidNotFoundException, InvalidBid, InvalidBidOfferPairException, InvalidTrade, MarketException)
from gsy_e.events import MarketEvent
from gsy_e.models.market import Bid, Offer
from gsy_e.models.market.two_sided import TwoSidedMarket


@pytest.fixture(name="market")
def fixture_market():
    return TwoSidedMarket(time_slot=pendulum.now(), bc=NonBlockchainInterface(str(uuid4())))


@pytest.fixture(name="pac_market")
def fixture_pac_market():
    return PayAsClearMatchingAlgorithm()


@pytest.fixture(name="market_matcher")
def fixture_market_matcher():
    return PayAsBidMatchingAlgorithm()


class TestTwoSidedMarket:
    """Class Responsible for testing two sided market"s functionality."""

    @staticmethod
    def test_two_sided_market_repr(market):
        """Test the __repr__ value of TwoSidedMarket."""
        assert market.__repr__() == (
            f"<TwoSidedMarket {market.time_slot_str} bids: {len(market.bids)}"
            f" (E: {sum(b.energy for b in market.bids.values())} kWh"
            f" V:{sum(b.price for b in market.bids.values())}) "
            f"offers: {len(market.offers)}"
            f" (E: {sum(o.energy for o in market.offers.values())} kWh"
            f" V: {sum(o.price for o in market.offers.values())})"
            f" trades: {len(market.trades)} (E: {market.accumulated_trade_energy} kWh,"
            f" V: {market.accumulated_trade_price})>"
        )

    @staticmethod
    def test_get_bids(market):
        """Test the get_bids() method of TwoSidedMarket."""
        market.bids = {
            "bid1": Bid("bid1", pendulum.now(), 9, 10, "B", 9,
                        buyer_id="bid_id"),
            "bid2": Bid("bid2", pendulum.now(), 9, 10, "B", 9,
                        buyer_id="bid_id"),
            "bid3": Bid("bid3", pendulum.now(), 9, 10, "B", 9,
                        buyer_id="bid_id")
        }
        assert market.get_bids() == market.bids

    @staticmethod
    def test_get_offers(market):
        """Test the get_offers() method of TwoSidedMarket."""
        market.offers = {
            "offer1": Offer("offer1", pendulum.now(), 2, 2, "other", 2,),
            "offer2": Offer("offer2", pendulum.now(), 2, 2, "other", 2,),
            "offer3": Offer("offer3", pendulum.now(), 2, 2, "other", 2,)
        }
        assert market.get_offers() == market.offers

    @staticmethod
    @patch("gsy_e.models.market.two_sided.TwoSidedMarket._update_new_bid_price_with_fee",
           MagicMock(return_value=5))
    def test_bid(market):
        """Test the bid() method of TwoSidedMarket."""
        # if energy < 0
        assert len(market.bids) == 0
        with pytest.raises(InvalidBid):
            market.bid(5, -2, "buyer", "buyer_origin")
            assert len(market.bids) == 0
        # if price < 0
        with pytest.raises(MarketException) as exception:
            market.bid(-5, -2, "buyer", "buyer_origin")
            assert exception.value == "Negative price after taxes, bid cannot be posted."
            assert len(market.bids) == 0

        bid = market.bid(5, 2, "buyer", "buyer_origin", bid_id="my_bid")
        assert len(market.bids) == 1
        assert "my_bid" in market.bids
        assert bid.energy == 2
        assert bid.price == 5
        assert bid in market.bid_history
        assert market._update_new_bid_price_with_fee.called

    @staticmethod
    def test_delete_bid(market):
        """Test the delete_bid method of TwoSidedMarket."""
        bid1 = Bid("bid1", pendulum.now(), 9, 10, "B", 9,
                   buyer_id="bid_id")
        bid2 = Bid("bid2", pendulum.now(), 9, 10, "B", 9,
                   buyer_id="bid_id")
        market.bids = {
            "bid1": bid1,
            "bid2": bid2,
        }
        market.delete_bid("bid1")
        assert "bid1" not in market.bids
        assert len(market.bids) == 1
        market.delete_bid(bid2)
        assert len(market.bids) == 0
        with pytest.raises(BidNotFoundException):
            market.delete_bid(bid2)

    @staticmethod
    def test_double_sided_validate_requirements_satisfied(market):
        offer = Offer("id", pendulum.now(), 2, 2, "other", 2,
                      requirements=[{"trading_partners": ["bid_id2"]}],
                      attributes={"energy_type": "Green"})
        bid = Bid("bid_id", pendulum.now(), 9, 10, "B", 9,
                  buyer_id="bid_id", requirements=[], attributes={})
        recommendation = BidOfferMatch(offer=offer, bid=bid, market_id="market",
                                       time_slot="2022-01-17T12:00",
                                       matching_requirements={
                                           "offer_requirement": offer.requirements[0]},
                                       selected_energy=2, trade_rate=0.5)
        with pytest.raises(InvalidBidOfferPairException):
            # should raise an exception as buyer_id is not in trading_partners
            market._validate_requirements_satisfied(recommendation)
        bid.buyer_id = "bid_id2"
        market._validate_requirements_satisfied(recommendation)  # Should not raise any exceptions
        # bid.requirements.append({"energy_type": ["Grey"]})
        recommendation.matching_requirements["bid_requirement"] = {"energy_type": ["Grey"]}
        with pytest.raises(InvalidBidOfferPairException):
            # should raise an exception as energy_type of offer needs to be in [Grey, ]
            market._validate_requirements_satisfied(recommendation)

        # Adding another requirement that is satisfied, should not raise an exception
        recommendation.matching_requirements["bid_requirement"] = {"energy_type": ["Green"]}
        market._validate_requirements_satisfied(recommendation)

    @staticmethod
    def test_validate_bid_offer_match_orders_do_not_exist(market):
        offer = Offer("id", pendulum.now(), 2, 1, "other", 2)
        bid = Bid("bid_id", pendulum.now(), 2, 1, "B", 8)
        recommendation = BidOfferMatch(bid=bid.serializable_dict(),
                                       offer=offer.serializable_dict(),
                                       trade_rate=2,
                                       selected_energy=1, market_id="market",
                                       time_slot="2022-01-17T12:00")
        with pytest.raises(InvalidBidOfferPairException) as exception:
            market.validate_bid_offer_match(recommendation)
            assert "Not all bids and offers exist in the market." in str(exception.value)

    @staticmethod
    @pytest.mark.parametrize(
        "bid_energy, offer_energy, clearing_rate, selected_energy", [
            (2, 3, 2, 2.5),
            (3, 2, 2, 2.5),
            (2, 2, 2, 2),
            (2, 2.5, 2, 2),
        ])
    def test_validate_bid_offer_match_raises_exception(
            market, bid_energy, offer_energy, clearing_rate, selected_energy):
        offer = Offer("id", pendulum.now(), 2, offer_energy, "other", 2)
        bid = Bid("bid_id", pendulum.now(), 2, bid_energy, "B", 8)
        market.bids = {"bid_id": bid}
        market.offers = {"id": offer}
        recommendation = BidOfferMatch(bid=bid.serializable_dict(),
                                       offer=offer.serializable_dict(),
                                       trade_rate=clearing_rate,
                                       selected_energy=selected_energy, market_id="market",
                                       time_slot="2022-01-17T12:00")
        with pytest.raises(InvalidBidOfferPairException):
            market.validate_bid_offer_match(recommendation)

    @staticmethod
    def test_double_sided_performs_pay_as_bid_matching(
            market: TwoSidedMarket, market_matcher):
        market.offers = {"offer1": Offer("id", pendulum.now(), 2, 2, "other", 2)}

        market.bids = {"bid1": Bid("bid_id", pendulum.now(), 9, 10, "B", buyer_origin="S")}
        matched = market_matcher.get_matches_recommendations({
            "Area1": {
                market.time_slot_str: {
                    "bids": [bid.serializable_dict() for bid in market.bids.values()],
                    "offers": [offer.serializable_dict() for offer in
                               market.offers.values()]}}})
        assert len(matched) == 0
        market.bids = {"bid1": Bid("bid_id", pendulum.now(), 11, 10, "B", buyer_origin="S")}
        matched = market_matcher.get_matches_recommendations({
            "Area1": {
                market.time_slot_str: {
                    "bids": [bid.serializable_dict() for bid in market.bids.values()],
                    "offers": [offer.serializable_dict() for offer in market.offers.values()]}}
        })
        assert len(matched) == 1

        assert matched[0]["bid"] == list(market.bids.values())[0].serializable_dict()
        assert matched[0]["offer"] == list(market.offers.values())[0].serializable_dict()

        market.bids = {"bid1": Bid("bid_id1", pendulum.now(), 11, 10, "B", buyer_origin="S"),
                       "bid2": Bid("bid_id2", pendulum.now(), 9, 10, "B", buyer_origin="S"),
                       "bid3": Bid("bid_id3", pendulum.now(), 12, 10, "B", buyer_origin="S")}
        matched = market_matcher.get_matches_recommendations({
            "Area1": {
                market.time_slot_str: {
                    "bids": [bid.serializable_dict() for bid in market.bids.values()],
                    "offers": [offer.serializable_dict() for offer in market.offers.values()]
                }
            }})
        assert len(matched) == 1
        assert matched[0]["bid"]["id"] == "bid_id3"
        assert matched[0]["bid"]["energy_rate"] == 1.2
        assert matched[0]["bid"]["energy"] == 10
        assert matched[0]["offer"] == list(market.offers.values())[0].serializable_dict()

    @staticmethod
    def test_market_bid(market: TwoSidedMarket):
        bid = market.bid(1, 2, "bidder", "bidder")
        assert market.bids[bid.id] == bid
        assert bid.price == 1
        assert bid.energy == 2
        assert bid.buyer == "bidder"
        assert len(bid.id) == 36

    @staticmethod
    def test_market_bid_accepts_bid_id(market: TwoSidedMarket):
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

    @staticmethod
    def test_market_bid_invalid(market: TwoSidedMarket):
        with pytest.raises(InvalidBid):
            market.bid(10, -1, "someone", "someone")

    @staticmethod
    def test_double_sided_pay_as_clear_market_works_with_floats(pac_market):
        ConstSettings.MASettings.PAY_AS_CLEAR_AGGREGATION_ALGORITHM = 1
        offers = [
            Offer("id1", pendulum.now(), 1.1, 1, "other").serializable_dict(),
            Offer("id2", pendulum.now(), 2.2, 1, "other").serializable_dict(),
            Offer("id3", pendulum.now(), 3.3, 1, "other").serializable_dict()]

        bids = [
            Bid("bid_id1", pendulum.now(), 3.3, 1, "B", buyer_origin="S").serializable_dict(),
            Bid("bid_id2", pendulum.now(), 2.2, 1, "B", buyer_origin="S").serializable_dict(),
            Bid("bid_id3", pendulum.now(), 1.1, 1, "B", buyer_origin="S").serializable_dict()]

        matched = pac_market.get_clearing_point(bids, offers, now(), str(uuid4()))
        assert matched.rate == 2.2

    @staticmethod
    def test_market_bid_trade():
        market = TwoSidedMarket(bc=MagicMock(), time_slot=pendulum.now())
        bid = market.bid(20, 10, "A", "A", original_price=20)
        trade_offer_info = TradeBidOfferInfo(2, 2, 0.5, 0.5, 2)
        trade = market.accept_bid(bid, energy=10, seller="B", trade_offer_info=trade_offer_info)
        assert trade
        assert trade.id == market.trades[0].id
        assert trade.id
        assert trade.trade_price == bid.price
        assert trade.traded_energy == bid.energy
        assert trade.seller == "B"
        assert trade.buyer == "A"
        assert not trade.residual

    @staticmethod
    def test_market_trade_bid_not_found(
            market=TwoSidedMarket(bc=MagicMock(), time_slot=pendulum.now())):
        bid = market.bid(20, 10, "A", "A")
        trade_offer_info = TradeBidOfferInfo(2, 2, 1, 1, 2)
        assert market.accept_bid(bid, 10, "B", trade_offer_info=trade_offer_info)

        with pytest.raises(BidNotFoundException):
            market.accept_bid(bid, 10, "B", trade_offer_info=trade_offer_info)

    @staticmethod
    def test_market_trade_bid_partial(
            market=TwoSidedMarket(bc=MagicMock(), time_slot=pendulum.now())):
        bid = market.bid(20, 20, "A", "A", original_price=20)
        trade_offer_info = TradeBidOfferInfo(1, 1, 1, 1, 1)
        trade = market.accept_bid(bid, energy=5, seller="B", trade_offer_info=trade_offer_info)
        assert trade
        assert trade.id == market.trades[0].id
        assert trade.id
        assert trade.offer_bid is not bid
        assert trade.traded_energy == 5
        assert trade.trade_price == 5
        assert trade.seller == "B"
        assert trade.buyer == "A"
        assert trade.residual
        assert len(market.bids) == 1
        assert trade.residual.id in market.bids
        assert market.bids[trade.residual.id].energy == 15
        assert isclose(market.bids[trade.residual.id].price, 15)
        assert market.bids[trade.residual.id].buyer == "A"

    @staticmethod
    def test_market_accept_bid_emits_bid_split_on_partial_bid(
            called, market=TwoSidedMarket(bc=MagicMock(), time_slot=pendulum.now())):
        market.add_listener(called)
        bid = market.bid(20, 20, "A", "A")
        trade_offer_info = TradeBidOfferInfo(1, 1, 1, 1, 1)
        trade = market.accept_bid(bid, energy=1, trade_offer_info=trade_offer_info)
        assert all(ev != repr(MarketEvent.BID_DELETED) for c in called.calls for ev in c[0])
        assert len(called.calls) == 2
        assert called.calls[0][0] == (repr(MarketEvent.BID_SPLIT),)
        assert called.calls[1][0] == (repr(MarketEvent.BID_TRADED),)
        assert called.calls[1][1] == {
            "market_id": repr(market.id),
            "bid_trade": repr(trade),
        }

    @staticmethod
    @pytest.mark.parametrize("market_method", ("_update_accumulated_trade_price_energy",
                                               "_update_min_max_avg_trade_prices"))
    def test_market_accept_bid_always_updates_trade_stats(
            called, market_method, market=TwoSidedMarket(bc=MagicMock(),
                                                         time_slot=pendulum.now())):
        setattr(market, market_method, called)

        bid = market.bid(20, 20, "A", "A")
        trade_offer_info = TradeBidOfferInfo(1, 1, 1, 1, 1)
        trade = market.accept_bid(bid, energy=5, seller="B", trade_offer_info=trade_offer_info)
        assert trade
        assert len(getattr(market, market_method).calls) == 1

    @staticmethod
    @pytest.mark.parametrize("energy", (0, 21, 100, -20))
    def test_market_trade_partial_bid_invalid(
            energy, market=TwoSidedMarket(bc=MagicMock(), time_slot=pendulum.now())):
        bid = market.bid(20, 20, "A", "A")
        trade_offer_info = TradeBidOfferInfo(1, 1, 1, 1, 1)
        with pytest.raises(InvalidTrade):
            market.accept_bid(bid, energy=energy, seller="A", trade_offer_info=trade_offer_info)

    @staticmethod
    def test_market_accept_bid_yields_partial_bid_trade(
            market=TwoSidedMarket(bc=MagicMock(), time_slot=pendulum.now())):
        bid = market.bid(2.0, 4, "buyer", "buyer")
        trade_offer_info = TradeBidOfferInfo(2, 2, 1, 1, 2)
        trade = market.accept_bid(bid, energy=1, seller="seller",
                                  trade_offer_info=trade_offer_info)
        assert trade.offer_bid.id == bid.id and trade.traded_energy == 1

    @staticmethod
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
    def test_double_sided_market_performs_pay_as_clear_matching(
            pac_market, offer, bid, mcp_rate, mcp_energy):
        ConstSettings.MASettings.PAY_AS_CLEAR_AGGREGATION_ALGORITHM = 1
        offers = [Offer("id1", pendulum.now(), offer[0], 1, "other").serializable_dict(),
                  Offer("id2", pendulum.now(), offer[1], 1, "other").serializable_dict(),
                  Offer("id3", pendulum.now(), offer[2], 1, "other").serializable_dict(),
                  Offer("id4", pendulum.now(), offer[3], 1, "other").serializable_dict(),
                  Offer("id5", pendulum.now(), offer[4], 1, "other").serializable_dict(),
                  Offer("id6", pendulum.now(), offer[5], 1, "other").serializable_dict(),
                  Offer("id7", pendulum.now(), offer[6], 1, "other").serializable_dict()]

        bids = [
            Bid("bid_id1", pendulum.now(), bid[0], 1, "B", buyer_origin="S").serializable_dict(),
            Bid("bid_id2", pendulum.now(), bid[1], 1, "B", buyer_origin="S").serializable_dict(),
            Bid("bid_id3", pendulum.now(), bid[2], 1, "B", buyer_origin="S").serializable_dict(),
            Bid("bid_id4", pendulum.now(), bid[3], 1, "B", buyer_origin="S").serializable_dict(),
            Bid("bid_id5", pendulum.now(), bid[4], 1, "B", buyer_origin="S").serializable_dict(),
            Bid("bid_id6", pendulum.now(), bid[5], 1, "B", buyer_origin="S").serializable_dict(),
            Bid("bid_id7", pendulum.now(), bid[6], 1, "B", buyer_origin="S").serializable_dict()
        ]

        clearing = pac_market.get_clearing_point(bids, offers, now(), str(uuid4()))
        assert clearing.rate == mcp_rate
        assert clearing.energy == mcp_energy

    @staticmethod
    def test_matching_list_gets_updated_with_residual_offers():
        matches = [
            BidOfferMatch(
                offer=Offer("offer_id", pendulum.now(), 1, 1, "S").serializable_dict(),
                selected_energy=1,
                bid=Bid("bid_id", pendulum.now(), 1, 1, "B").serializable_dict(),
                trade_rate=1,
                market_id="",
                time_slot="").serializable_dict(),
            BidOfferMatch(
                offer=Offer("offer_id2", pendulum.now(), 2, 2, "S").serializable_dict(),
                selected_energy=2,
                bid=Bid("bid_id2", pendulum.now(), 2, 2, "B").serializable_dict(),
                trade_rate=1,
                market_id="",
                time_slot="").serializable_dict()
        ]
        offer_trade = Trade("trade", 1, Offer("offer_id", pendulum.now(), 1, 1, "S"), "S", "B",
                            residual=Offer("residual_offer", pendulum.now(), 0.5, 0.5, "S"),
                            traded_energy=1, trade_price=1)
        bid_trade = Trade("bid_trade", 1, Bid("bid_id2", pendulum.now(), 1, 1, "S"), "S", "B",
                          residual=Bid("residual_bid_2", pendulum.now(), 1, 1, "S"),
                          traded_energy=1, trade_price=1)
        matches = TwoSidedMarket._replace_offers_bids_with_residual_in_recommendations_list(
            matches, offer_trade, bid_trade
        )
        assert len(matches) == 2
        assert matches[0]["offer"]["id"] == "residual_offer"
        assert matches[1]["bid"]["id"] == "residual_bid_2"


class TestTwoSidedMarketMatchRecommendations:
    """Class Responsible for testing two sided market's matching functionality."""

    @staticmethod
    def test_match_recommendations(market):
        """Test match_recommendations() method of TwoSidedMarket."""
        bid = Bid("bid_id1", pendulum.now(),
                  price=2, energy=1, buyer="Buyer", time_slot="2021-10-06T12:00")
        offer = Offer("offer_id1", pendulum.now(),
                      price=2, energy=1, seller="Seller", time_slot="2021-10-06T12:00")

        market.bids = {"bid_id1": bid}
        market.offers = {"offer_id1": offer}

        recommendations = [
            BidOfferMatch(
                bid=bid.serializable_dict(), offer=offer.serializable_dict(),
                trade_rate=2, selected_energy=1, market_id=market.id,
                time_slot="2021-10-06T12:00").serializable_dict()
        ]
        market.match_recommendations(recommendations)
        assert len(market.trades) == 1
