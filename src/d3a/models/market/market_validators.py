"""
Copyright 2018 Grid Singularity
This file is part of D3A.
This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.
You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""


from abc import ABC, abstractmethod
from typing import Dict, Optional

from d3a.models.market import Offer, Bid


class Requirement(ABC):
    """Interface for offer and bid requirements."""

    @classmethod
    @abstractmethod
    def is_satisfied(
            cls, offer: Offer, bid: Bid, requirement: Dict,
            clearing_rate: float = None, selected_energy: float = None) -> bool:
        """Check whether a requirement is satisfied."""


class TradingPartnersRequirement(Requirement):
    """Check if trading_partners requirement is satisfied for both bid and offer."""

    @classmethod
    def is_satisfied(cls, offer: Offer, bid: Bid, requirement: Dict,
                     clearing_rate: Optional[float] = None,
                     selected_energy: Optional[float] = None) -> bool:
        trading_partners = requirement.get("trading_partners")
        assert isinstance(trading_partners, list),\
            f"Invalid data type for trading partner {requirement}"
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
    def is_satisfied(cls, offer: Offer, bid: Bid, requirement: Dict,
                     clearing_rate: Optional[float] = None,
                     selected_energy: Optional[float] = None) -> bool:
        bid_required_energy_types = requirement.get("energy_type")
        assert isinstance(bid_required_energy_types, list), \
            f"Invalid data type for energy_type {requirement}"
        offer_energy_type = (
                offer.attributes or {}).get("energy_type", None)
        # bid_required_energy_types is None or it is defined & includes offer_energy_type -> true
        return not bid_required_energy_types or offer_energy_type in bid_required_energy_types


class SelectedEnergyRequirement(Requirement):
    """Check if energy (selected energy) requirement of bid is satisfied."""

    @classmethod
    def is_satisfied(cls, offer: Offer, bid: Bid, requirement: Dict,
                     clearing_rate: Optional[float] = None,
                     selected_energy: Optional[float] = None) -> bool:
        bid_required_energy = requirement.get("energy")
        assert isinstance(bid_required_energy, (int, float)), \
            f"Invalid data type for energy {requirement}"
        assert isinstance(selected_energy, (int, float)), \
            f"Invalid data type for selected_energy {selected_energy}"
        # bid_required_energy is None or it is defined & equals selected_energy -> true
        return bid_required_energy >= selected_energy


class ClearingRateRequirement(Requirement):
    """Check if price (clearing rate) requirement of bid is satisfied."""

    @classmethod
    def is_satisfied(cls, offer: Offer, bid: Bid, requirement: Dict,
                     clearing_rate: Optional[float] = None,
                     selected_energy: Optional[float] = None) -> bool:
        bid_required_price = requirement.get("price")
        assert isinstance(bid_required_price, (int, float)), \
            f"Invalid data type for energy {requirement}"
        assert isinstance(clearing_rate, (int, float)), \
            f"Invalid data type for clearing_rate {clearing_rate}"
        # bid_required_energy is None or it is defined & equals selected_energy -> true
        return bid_required_price >= clearing_rate


# Supported offers/bids requirements
# To add a new requirement create a class extending the Requirement abstract class and add it below

SUPPORTED_OFFER_REQUIREMENTS = {
    "trading_partners": TradingPartnersRequirement
}

SUPPORTED_BID_REQUIREMENTS = {
    "trading_partners": TradingPartnersRequirement,
    "energy_type": EnergyTypeRequirement,
    "energy": SelectedEnergyRequirement,
    "price": ClearingRateRequirement
}


class RequirementsSatisfiedChecker:
    """Check if a list of bid/offer requirements are satisfied."""

    @classmethod
    def is_satisfied(
            cls, offer: Offer, bid: Bid,
            clearing_rate: Optional[float] = None,
            selected_energy: Optional[float] = None) -> bool:
        """Receive offer and bid and validate that at least 1 requirement is satisfied."""
        offer_requirements = offer.requirements or []
        bid_requirements = bid.requirements or []

        # If concerned bid or offer have no requirements, consider it as satisfied.
        offer_requirement_satisfied = not offer_requirements
        bid_requirement_satisfied = not bid_requirements

        for requirement in offer_requirements:
            if all(key in SUPPORTED_OFFER_REQUIREMENTS
                   and SUPPORTED_OFFER_REQUIREMENTS[key].is_satisfied(
                        offer, bid, requirement, clearing_rate, selected_energy)
                    for key in requirement):
                offer_requirement_satisfied = True
                break

        for requirement in bid_requirements:
            if all(key in SUPPORTED_BID_REQUIREMENTS
                   and SUPPORTED_BID_REQUIREMENTS[key].is_satisfied(
                        offer, bid, requirement, clearing_rate, selected_energy)
                   for key in requirement):
                bid_requirement_satisfied = True
                break

        return offer_requirement_satisfied and bid_requirement_satisfied
