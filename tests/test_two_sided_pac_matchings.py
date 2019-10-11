import unittest
from parameterized import parameterized
from d3a.models.market.market_structures import Bid, Offer, BidOfferMatch, Trade
from d3a.models.market.two_sided_pay_as_clear import TwoSidedPayAsClear


class TestCreateBidOfferMatchings(unittest.TestCase):

    def validate_matching(self, matching, matched_energy, offer_id, bid_id):
        assert matching.offer_energy == matched_energy
        assert matching.offer.id == offer_id
        assert matching.bid_energy == matched_energy
        assert matching.bid.id == bid_id

    @parameterized.expand([
        (1, 2, 3, 4, 5, 15),
        (5, 4, 3, 2, 1, 15),
        (12, 123, 432, 543, 1, 1111.2),
        (867867.61, 123.98, 432.43, 12.12, 0.001, 868440)
    ])
    def test_create_bid_offer_matchings_respects_offer_bid_order(
            self, en1, en2, en3, en4, en5, clearing_energy
    ):
        bid_list = [
            Bid('bid_id', 1, en1, 'B', 'S'),
            Bid('bid_id1', 2, en2, 'B', 'S'),
            Bid('bid_id2', 3, en3, 'B', 'S'),
            Bid('bid_id3', 4, en4, 'B', 'S'),
            Bid('bid_id4', 5, en5, 'B', 'S')
        ]

        offer_list = [
            Offer('offer_id', 1, en1, 'S'),
            Offer('offer_id1', 2, en2, 'S'),
            Offer('offer_id2', 3, en3, 'S'),
            Offer('offer_id3', 4, en4, 'S'),
            Offer('offer_id4', 5, en5, 'S')
        ]

        matchings = TwoSidedPayAsClear._create_bid_offer_matchings(
            clearing_energy, offer_list, bid_list
        )

        assert len(matchings) == 5
        self.validate_matching(matchings[0], en1, 'offer_id', 'bid_id')
        self.validate_matching(matchings[1], en2, 'offer_id1', 'bid_id1')
        self.validate_matching(matchings[2], en3, 'offer_id2', 'bid_id2')
        self.validate_matching(matchings[3], en4, 'offer_id3', 'bid_id3')
        self.validate_matching(matchings[4], en5, 'offer_id4', 'bid_id4')

    def test_create_bid_offer_matchings_can_handle_partial_bids(self):
        bid_list = [
            Bid('bid_id', 9, 9, 'B', 'S'),
            Bid('bid_id1', 3, 3, 'B', 'S'),
            Bid('bid_id2', 3, 3, 'B', 'S'),
        ]

        offer_list = [
            Offer('offer_id', 1, 1, 'S'),
            Offer('offer_id1', 2, 2, 'S'),
            Offer('offer_id2', 3, 3, 'S'),
            Offer('offer_id3', 4, 4, 'S'),
            Offer('offer_id4', 5, 5, 'S')
        ]

        matchings = TwoSidedPayAsClear._create_bid_offer_matchings(15, offer_list, bid_list)

        assert len(matchings) == 7
        self.validate_matching(matchings[0], 1, 'offer_id', 'bid_id')
        self.validate_matching(matchings[1], 2, 'offer_id1', 'bid_id')
        self.validate_matching(matchings[2], 3, 'offer_id2', 'bid_id')
        self.validate_matching(matchings[3], 3, 'offer_id3', 'bid_id')
        self.validate_matching(matchings[4], 1, 'offer_id3', 'bid_id1')
        self.validate_matching(matchings[5], 2, 'offer_id4', 'bid_id1')
        self.validate_matching(matchings[6], 3, 'offer_id4', 'bid_id2')

    def test_create_bid_offer_matchings_can_handle_partial_offers(self):
        bid_list = [
            Bid('bid_id', 1, 1, 'B', 'S'),
            Bid('bid_id1', 2, 2, 'B', 'S'),
            Bid('bid_id2', 3, 3, 'B', 'S'),
            Bid('bid_id3', 4, 4, 'B', 'S'),
            Bid('bid_id4', 5, 5, 'B', 'S')
        ]

        offer_list = [
            Offer('offer_id', 8, 8, 'S'),
            Offer('offer_id1', 4, 4, 'S'),
            Offer('offer_id2', 3, 3, 'S'),
        ]

        matchings = TwoSidedPayAsClear._create_bid_offer_matchings(15, offer_list, bid_list)

        self.validate_matching(matchings[0], 1, 'offer_id', 'bid_id')
        self.validate_matching(matchings[1], 2, 'offer_id', 'bid_id1')
        self.validate_matching(matchings[2], 3, 'offer_id', 'bid_id2')
        self.validate_matching(matchings[3], 2, 'offer_id', 'bid_id3')
        self.validate_matching(matchings[4], 2, 'offer_id1', 'bid_id3')
        self.validate_matching(matchings[5], 2, 'offer_id1', 'bid_id4')
        self.validate_matching(matchings[6], 3, 'offer_id2', 'bid_id4')

    def test_create_bid_offer_matchings_can_handle_excessive_offer_energy(self):
        bid_list = [
            Bid('bid_id', 1, 1, 'B', 'S'),
            Bid('bid_id1', 2, 2, 'B', 'S'),
            Bid('bid_id2', 3, 3, 'B', 'S'),
            Bid('bid_id3', 4, 4, 'B', 'S'),
            Bid('bid_id4', 5, 5, 'B', 'S')
        ]

        offer_list = [
            Offer('offer_id', 8, 8, 'S'),
            Offer('offer_id1', 4, 4, 'S'),
            Offer('offer_id2', 13, 13, 'S'),
        ]

        matchings = TwoSidedPayAsClear._create_bid_offer_matchings(15, offer_list, bid_list)

        assert len(matchings) == 7
        self.validate_matching(matchings[0], 1, 'offer_id', 'bid_id')
        self.validate_matching(matchings[1], 2, 'offer_id', 'bid_id1')
        self.validate_matching(matchings[2], 3, 'offer_id', 'bid_id2')
        self.validate_matching(matchings[3], 2, 'offer_id', 'bid_id3')
        self.validate_matching(matchings[4], 2, 'offer_id1', 'bid_id3')
        self.validate_matching(matchings[5], 2, 'offer_id1', 'bid_id4')
        self.validate_matching(matchings[6], 3, 'offer_id2', 'bid_id4')

    def test_create_bid_offer_matchings_can_handle_excessive_bid_energy(self):
        bid_list = [
            Bid('bid_id', 1, 1, 'B', 'S'),
            Bid('bid_id1', 2, 2, 'B', 'S'),
            Bid('bid_id2', 3, 3, 'B', 'S'),
            Bid('bid_id3', 4, 4, 'B', 'S'),
            Bid('bid_id4', 5, 5, 'B', 'S')
        ]

        offer_list = [
            Offer('offer_id', 8, 8, 'S'),
            Offer('offer_id1', 4, 4, 'S'),
            Offer('offer_id2', 5003, 5003, 'S'),
        ]

        matchings = TwoSidedPayAsClear._create_bid_offer_matchings(15, offer_list, bid_list)

        assert len(matchings) == 7
        self.validate_matching(matchings[0], 1, 'offer_id', 'bid_id')
        self.validate_matching(matchings[1], 2, 'offer_id', 'bid_id1')
        self.validate_matching(matchings[2], 3, 'offer_id', 'bid_id2')
        self.validate_matching(matchings[3], 2, 'offer_id', 'bid_id3')
        self.validate_matching(matchings[4], 2, 'offer_id1', 'bid_id3')
        self.validate_matching(matchings[5], 2, 'offer_id1', 'bid_id4')
        self.validate_matching(matchings[6], 3, 'offer_id2', 'bid_id4')

    def test_create_bid_offer_matchings_can_match_with_only_one_offer(self):
        bid_list = [
            Bid('bid_id', 1, 1, 'B', 'S'),
            Bid('bid_id1', 2, 2, 'B', 'S'),
            Bid('bid_id2', 3, 3, 'B', 'S'),
            Bid('bid_id3', 4, 4, 'B', 'S'),
            Bid('bid_id4', 5, 5, 'B', 'S')
        ]

        offer_list = [
            Offer('offer_id', 8, 800000000, 'S')
        ]

        matchings = TwoSidedPayAsClear._create_bid_offer_matchings(15, offer_list, bid_list)

        assert len(matchings) == 5
        self.validate_matching(matchings[0], 1, 'offer_id', 'bid_id')
        self.validate_matching(matchings[1], 2, 'offer_id', 'bid_id1')
        self.validate_matching(matchings[2], 3, 'offer_id', 'bid_id2')
        self.validate_matching(matchings[3], 4, 'offer_id', 'bid_id3')
        self.validate_matching(matchings[4], 5, 'offer_id', 'bid_id4')

    def test_create_bid_offer_matchings_can_match_with_only_one_bid(self):
        bid_list = [
            Bid('bid_id', 9, 90123456789, 'B', 'S')
        ]

        offer_list = [
            Offer('offer_id', 1, 1, 'S'),
            Offer('offer_id1', 2, 2, 'S'),
            Offer('offer_id2', 3, 3, 'S'),
            Offer('offer_id3', 4, 4, 'S'),
            Offer('offer_id4', 5, 5, 'S')
        ]

        matchings = TwoSidedPayAsClear._create_bid_offer_matchings(15, offer_list, bid_list)

        assert len(matchings) == 5
        self.validate_matching(matchings[0], 1, 'offer_id', 'bid_id')
        self.validate_matching(matchings[1], 2, 'offer_id1', 'bid_id')
        self.validate_matching(matchings[2], 3, 'offer_id2', 'bid_id')
        self.validate_matching(matchings[3], 4, 'offer_id3', 'bid_id')
        self.validate_matching(matchings[4], 5, 'offer_id4', 'bid_id')

    def test_matching_list_gets_updated_with_residual_offers(self):
        matchings = [
            BidOfferMatch(offer=Offer('offer_id', 1, 1, 'S'), offer_energy=1,
                          bid=Bid('bid_id', 1, 1, 'B', 'S'), bid_energy=1),
            BidOfferMatch(offer=Offer('offer_id2', 2, 2, 'S'), offer_energy=2,
                          bid=Bid('bid_id2', 2, 2, 'B', 'S'), bid_energy=2)
        ]

        offer_trade = Trade('trade', 1, Offer('offer_id', 1, 1, 'S'), 'S', 'B',
                            residual=Offer('residual_offer', 0.5, 0.5, 'S'))
        bid_trade = Trade('bid_trade', 1, Bid('bid_id2', 1, 1, 'S', 'B'), 'S', 'B',
                          residual=Bid('residual_bid_2', 1, 1, 'S', 'B'))

        matchings = TwoSidedPayAsClear._replace_offers_bids_with_residual_in_matching_list(
            matchings, 0, offer_trade, bid_trade
        )
        assert len(matchings) == 2
        assert matchings[0].offer.id == 'residual_offer'
        assert matchings[1].bid.id == 'residual_bid_2'

    def test_matching_list_affects_only_matches_after_start_index(self):
        matchings = [
            BidOfferMatch(offer=Offer('offer_id', 1, 1, 'S'), offer_energy=1,
                          bid=Bid('bid_id', 1, 1, 'B', 'S'), bid_energy=1),
            BidOfferMatch(offer=Offer('offer_id2', 2, 2, 'S'), offer_energy=2,
                          bid=Bid('bid_id2', 2, 2, 'B', 'S'), bid_energy=2),
            BidOfferMatch(offer=Offer('offer_id', 1, 1, 'S'), offer_energy=1,
                          bid=Bid('bid_id', 1, 1, 'B', 'S'), bid_energy=1)
        ]

        offer_trade = Trade('trade', 1, Offer('offer_id', 1, 1, 'S'), 'S', 'B',
                            residual=Offer('residual_offer', 0.5, 0.5, 'S'))
        bid_trade = Trade('bid_trade', 1, Bid('bid_id2', 1, 1, 'S', 'B'), 'S', 'B',
                          residual=Bid('residual_bid_2', 1, 1, 'S', 'B'))

        matchings = TwoSidedPayAsClear._replace_offers_bids_with_residual_in_matching_list(
            matchings, 1, offer_trade, bid_trade
        )
        assert len(matchings) == 3
        assert matchings[0].offer.id == 'offer_id'
        assert matchings[1].bid.id == 'residual_bid_2'
        assert matchings[2].offer.id == 'residual_offer'
