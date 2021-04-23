from d3a.constants import DOUBLE_SIDED_ALGO
from d3a.models.myco_matcher.pay_as_bid import PayAsBidMatch
from d3a.models.myco_matcher.pay_as_clear import PayAsClear


class MycoMatcher:
    def __init__(self):
        self.bid_offer_pairs = []
        if DOUBLE_SIDED_ALGO == 1:
            self.match_algo = PayAsBidMatch()
        elif DOUBLE_SIDED_ALGO == 2:
            self.match_algo = PayAsClear()

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

    def calculate_recommendation(self, bids, offers):
        self.bid_offer_pairs = []

        self.bid_offer_pairs = self.match_algo.calculate_match_recommend(bids, offers)
