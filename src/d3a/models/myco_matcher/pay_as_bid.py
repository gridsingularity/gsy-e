from d3a.constants import FLOATING_POINT_TOLERANCE
from d3a.models.market.market_structures import BidOfferMatch
from d3a.models.myco_matcher.base_matcher import BaseMatcher


class PayAsBidMatch(BaseMatcher):

    def calculate_match_recommendation(self, bids, offers):
        """
        Pay as bid first
        There are 2 simplistic approaches to the problem
        1. Match the cheapest offer with the most expensive bid. This will favor the sellers
        2. Match the cheapest offer with the cheapest bid. This will favor the buyers,
           since the most affordable offers will be allocated for the most aggressive buyers.
        """

        # Sorted bids in descending order
        sorted_bids = self.sort_by_energy_rate(bids, True)

        # Sorted offers in descending order
        sorted_offers = self.sort_by_energy_rate(offers, True)

        already_selected_bids = set()
        bid_offer_pairs = []
        for offer in sorted_offers:
            for bid in sorted_bids:
                if bid.id in already_selected_bids or offer.seller == bid.buyer:
                    continue
                if (bid.energy_rate - offer.energy_rate) > FLOATING_POINT_TOLERANCE:
                    already_selected_bids.add(bid.id)
                    selected_energy = min(bid.energy, offer.energy)
                    bid_offer_pairs.append(BidOfferMatch(
                        bid=bid, offer=offer, bid_energy=selected_energy,
                        offer_energy=selected_energy, trade_rate=bid.energy_rate))
                    break
        return bid_offer_pairs
