from d3a.constants import FLOATING_POINT_TOLERANCE


class PayAsBidMatch:
    def __init__(self):
        pass

    @staticmethod
    def sorting(obj, reverse_order=False):
        if reverse_order:
            # Sorted bids in descending order
            return list(reversed(sorted(
                obj.values(),
                key=lambda b: b.energy_rate)))

        else:
            # Sorted bids in ascending order
            return list(sorted(
                obj.values(),
                key=lambda b: b.energy_rate))

    def calculate_match_recommend(self, bids, offers):
        # Pay as bid first
        # There are 2 simplistic approaches to the problem
        # 1. Match the cheapest offer with the most expensive bid. This will favor the sellers
        # 2. Match the cheapest offer with the cheapest bid. This will favor the buyers,
        #    since the most affordable offers will be allocated for the most aggressive buyers.

        # Sorted bids in descending order
        sorted_bids = self.sorting(bids, True)

        # Sorted offers in descending order
        sorted_offers = self.sorting(offers, True)

        already_selected_bids = set()
        bid_offer_pairs = []
        for offer in sorted_offers:
            for bid in sorted_bids:
                if bid.id not in already_selected_bids and \
                        (offer.energy_rate - bid.energy_rate) <= \
                        FLOATING_POINT_TOLERANCE and offer.seller != bid.buyer:
                    already_selected_bids.add(bid.id)
                    bid_offer_pairs.append(tuple((bid, offer, bid.energy_rate)))
                    break
        return bid_offer_pairs
