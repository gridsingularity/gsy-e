"""Module containing filters to be applied to incoming orders received from external strategies."""

from typing import Dict, Tuple, Set


class DegreesOfFreedomFilter:
    """Remove the Degrees of Freedom fields from an incoming order."""
    FIELDS = ("requirements", "attributes")

    @classmethod
    def apply(cls, order: Dict) -> Tuple[Dict, Set[str]]:
        """Remove Degrees of Freedom fields from an order's attributes.

        The order dictionary is modified in-place.
        Args:
            order: a dictionary of arguments describing a bid or an offer.
        """
        filtered_fields = set()
        for field in cls.FIELDS:
            if order.get(field):
                order.pop(field)
                filtered_fields.add(field)

        return order, filtered_fields
