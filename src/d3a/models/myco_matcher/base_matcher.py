from abc import ABC, abstractmethod


class BaseMatcher(ABC):
    def __init__(self):
        pass

    @staticmethod
    def sort_by_energy_rate(obj, reverse_order=False):
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

    @abstractmethod
    def calculate_match_recommendation(self, bids, offers, current_time=None):
        pass
