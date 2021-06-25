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


class PreferredPartnersRequirement(Requirement):
    """Check if preferred_trading_partners requirement is satisfied for both bid and offer."""

    @classmethod
    def is_satisfied(cls, offer: Offer, bid: Bid, requirement: Dict) -> bool:
        preferred_trading_partners = requirement.get("preferred_trading_partners", [])
        assert isinstance(preferred_trading_partners, list),\
            f"Invalid requirement {requirement}"
        if preferred_trading_partners and not (
                bid.buyer_id in preferred_trading_partners or
                bid.buyer_origin_id in preferred_trading_partners or
                offer.seller_id in preferred_trading_partners or
                offer.seller_origin_id in preferred_trading_partners):
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
        if bid_required_energy_types and offer_energy_type not in bid_required_energy_types:
            return False
        return True


class HashedIdentityRequirement(Requirement):
    """Check if hashed_identity requirement of bid is satisfied."""

    @classmethod
    def is_satisfied(cls, offer: Offer, bid: Bid, requirement: Dict) -> bool:
        bid_required_hashed_identity = requirement.get("hashed_identity", "")
        assert isinstance(bid_required_hashed_identity, str), \
            f"Invalid requirement {requirement}"
        offer_hashed_identity = (
                offer.attributes or {}).get("hashed_identity", None)
        if bid_required_hashed_identity and offer_hashed_identity != bid_required_hashed_identity:
            return False
        return True


# Supported offers/bids requirements
# To add a new requirement create a class extending the Requirement abstract class and add it below
SUPPORTED_REQUIREMENTS_MAPPING = {
    "preferred_trading_partners": PreferredPartnersRequirement,
    "energy_type": EnergyTypeRequirement,
    "hashed_identity": HashedIdentityRequirement
}


class RequirementsSatisfiedChecker:
    """Check if a list of bid/offer requirements are satisfied."""

    @classmethod
    def is_satisfied(cls, offer: Offer, bid: Bid) -> bool:
        """Receive offer and bid and validate that at least 1 requirement is satisfied."""
        offer_requirements = getattr(offer, "requirements") or []
        bid_requirements = getattr(bid, "requirements") or []

        # If a bid of offer has no requirements, consider it as satisfied.
        offer_requirement_satisfied = True if not offer_requirements else False
        bid_requirement_satisfied = True if not bid_requirements else False

        for requirement in offer_requirements:
            if all(SUPPORTED_REQUIREMENTS_MAPPING[key].is_satisfied(offer, bid, requirement)
                    for key in requirement):
                offer_requirement_satisfied = True
                break

        for requirement in bid_requirements:
            if all(SUPPORTED_REQUIREMENTS_MAPPING[key].is_satisfied(offer, bid, requirement)
                   for key in requirement):
                bid_requirement_satisfied = True
                break

        return offer_requirement_satisfied and bid_requirement_satisfied
