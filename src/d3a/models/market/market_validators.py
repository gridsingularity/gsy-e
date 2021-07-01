"""Validators for d3a markets."""

from abc import ABC, abstractmethod
from typing import Dict

from d3a.models.market import Offer, Bid


class Requirement(ABC):
    """Define an offer/bid requirement with is_satisfied interface."""

    @classmethod
    @abstractmethod
    def is_satisfied(cls, offer: Offer, bid: Bid, requirement: Dict) -> bool:
        """Check whether a requirement is satisfied."""


class TradingPartnersRequirement(Requirement):
    """Check if trading_partners requirement is satisfied for both bid and offer."""

    @classmethod
    def is_satisfied(cls, offer: Offer, bid: Bid, requirement: Dict) -> bool:
        trading_partners = requirement.get("trading_partners", [])
        assert isinstance(trading_partners, list),\
            f"Invalid requirement {requirement}"
        if trading_partners and not (
                bid.buyer_id in trading_partners or
                bid.buyer_origin_id in trading_partners or
                offer.seller_id in trading_partners or
                offer.seller_origin_id in trading_partners):
            return False
        return True


class EnergyTypeRequirement(Requirement):
    """Check if energy_type requirement of bid is satisfied."""

    @classmethod
    def is_satisfied(cls, offer: Offer, bid: Bid, requirement: Dict) -> bool:
        bid_required_energy_types = requirement.get("energy_type", [])
        assert isinstance(bid_required_energy_types, list), \
            f"Invalid requirement {requirement}"
        offer_energy_type = (
                offer.attributes or {}).get("energy_type", None)
        # bid_required_energy_types is None or it is defined & includes offer_energy_type -> true
        return not bid_required_energy_types or offer_energy_type in bid_required_energy_types


# Supported offers/bids requirements
# To add a new requirement create a class extending the Requirement abstract class and add it below

SUPPORTED_OFFER_REQUIREMENTS = {
    "trading_partners": TradingPartnersRequirement
}

SUPPORTED_BID_REQUIREMENTS = {
    "trading_partners": TradingPartnersRequirement,
    "energy_type": EnergyTypeRequirement,
}


class RequirementsSatisfiedChecker:
    """Check if a list of bid/offer requirements are satisfied."""

    @classmethod
    def is_satisfied(cls, offer: Offer, bid: Bid) -> bool:
        """Receive offer and bid and validate that at least 1 requirement is satisfied."""
        offer_requirements = offer.requirements or []
        bid_requirements = bid.requirements or []

        # If a bid of offer has no requirements, consider it as satisfied.
        offer_requirement_satisfied = not offer_requirements
        bid_requirement_satisfied = not bid_requirements

        for requirement in offer_requirements:
            if all(key in SUPPORTED_OFFER_REQUIREMENTS
                   and SUPPORTED_OFFER_REQUIREMENTS[key].is_satisfied(offer, bid, requirement)
                    for key in requirement):
                offer_requirement_satisfied = True
                break

        for requirement in bid_requirements:
            if all(key in SUPPORTED_BID_REQUIREMENTS
                   and SUPPORTED_BID_REQUIREMENTS[key].is_satisfied(offer, bid, requirement)
                   for key in requirement):
                bid_requirement_satisfied = True
                break

        return offer_requirement_satisfied and bid_requirement_satisfied
