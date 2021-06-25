import pytest
from d3a.models.market import Offer, Bid
from d3a.models.market.market_validators import PreferredPartnersRequirement, \
    EnergyTypeRequirement, HashedIdentityRequirement, RequirementsSatisfiedChecker
from pendulum import now


@pytest.fixture
def offer():
    return Offer("id", now(), 2, 2, "other", 2)


@pytest.fixture
def bid():
    return Bid("bid_id", now(), 9, 10, "B", 9)


class TestRequirementsValidator:
    """Test all bid/offer requirements validators."""

    def test_preferred_partners_requirement(self, offer, bid):
        requirement = {}
        # Should be True as there are no preferred_trading_partners requirement
        assert PreferredPartnersRequirement.is_satisfied(offer, bid, requirement) is True

        # Test offer requirement
        bid.buyer_id = "buyer"
        requirement = {"preferred_trading_partners": ["buyer1"]}
        offer.requirements = [requirement]
        assert PreferredPartnersRequirement.is_satisfied(offer, bid, requirement) is False
        requirement = {"preferred_trading_partners": ["buyer"]}
        offer.requirements = [requirement]
        assert PreferredPartnersRequirement.is_satisfied(offer, bid, requirement) is True
        bid.buyer_id = "buyer1"
        bid.buyer_origin_id = "buyer"
        # still should pass
        assert PreferredPartnersRequirement.is_satisfied(offer, bid, requirement) is True

        # Test bid requirement
        offer.seller_id = "seller"
        requirement = {"preferred_trading_partners": ["seller1"]}
        bid.requirements = [requirement]
        assert PreferredPartnersRequirement.is_satisfied(offer, bid, requirement) is False
        requirement = {"preferred_trading_partners": ["seller"]}
        bid.requirements = [requirement]
        assert PreferredPartnersRequirement.is_satisfied(offer, bid, requirement) is True
        offer.seller_id = "seller1"
        offer.seller_origin_id = "seller"
        # still should pass
        assert PreferredPartnersRequirement.is_satisfied(offer, bid, requirement) is True

    def test_energy_type_requirement(self, offer, bid):
        requirement = {}
        # Should be True as there are no energy_type requirement
        assert EnergyTypeRequirement.is_satisfied(offer, bid, requirement) is True

        offer.attributes = {"energy_type": "Green"}
        requirement = {"energy_type": ["Grey"]}
        bid.requirements = [requirement]
        assert EnergyTypeRequirement.is_satisfied(offer, bid, requirement) is False
        requirement = {"energy_type": ["Grey", "Green"]}
        assert EnergyTypeRequirement.is_satisfied(offer, bid, requirement) is True

    def test_hashed_identity_requirement(self, offer, bid):
        requirement = {}
        # Should be True as there are no hashed_identity requirement
        assert HashedIdentityRequirement.is_satisfied(offer, bid, requirement) is True

        offer.attributes = {"hashed_identity": "x"}
        requirement = {"hashed_identity": "y"}
        bid.requirements = [requirement]
        assert HashedIdentityRequirement.is_satisfied(offer, bid, requirement) is False
        requirement = {"hashed_identity": "x"}
        bid.requirements = [requirement]
        assert HashedIdentityRequirement.is_satisfied(offer, bid, requirement) is True

    def test_requirements_validator(self, offer, bid):
        # should pass as no bid and offer have no requirements
        # assert RequirementsSatisfiedChecker.is_satisfied(offer, bid) is True

        offer.requirements = [{"preferred_trading_partners": ["x"]}]
        # assert RequirementsSatisfiedChecker.is_satisfied(offer, bid) is False
        # Empty requirement, should be satisfied
        offer.requirements.append({})
        assert RequirementsSatisfiedChecker.is_satisfied(offer, bid) is True

        offer.requirements = [{"preferred_trading_partners": ["x"]}]
        bid.buyer_origin_id = "x"
        assert RequirementsSatisfiedChecker.is_satisfied(offer, bid) is True
