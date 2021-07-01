import pytest
from pendulum import now
from unittest.mock import MagicMock, patch
from d3a.models.market import Bid, Offer
from d3a.models.market.market_validators import (
    EnergyTypeRequirement,
    TradingPartnersRequirement,
    RequirementsSatisfiedChecker)


@pytest.fixture
def offer():
    return Offer("id", now(), 2, 2, "other", 2)


@pytest.fixture
def bid():
    return Bid("bid_id", now(), 9, 10, "B", 9)


class TestRequirementsValidator:
    """Test all bid/offer requirements validators."""

    def test_trading_partners_requirement(self, offer, bid):
        requirement = {}
        # Should be True as there are no trading_partners requirement
        assert TradingPartnersRequirement.is_satisfied(offer, bid, requirement) is True

        # Test offer requirement
        bid.buyer_id = "buyer"
        requirement = {"trading_partners": ["buyer1"]}
        offer.requirements = [requirement]
        assert TradingPartnersRequirement.is_satisfied(offer, bid, requirement) is False
        requirement = {"trading_partners": ["buyer"]}
        offer.requirements = [requirement]
        assert TradingPartnersRequirement.is_satisfied(offer, bid, requirement) is True
        bid.buyer_id = "buyer1"
        bid.buyer_origin_id = "buyer"
        # still should pass
        assert TradingPartnersRequirement.is_satisfied(offer, bid, requirement) is True

        # Test bid requirement
        offer.seller_id = "seller"
        requirement = {"trading_partners": ["seller1"]}
        bid.requirements = [requirement]
        assert TradingPartnersRequirement.is_satisfied(offer, bid, requirement) is False
        requirement = {"trading_partners": ["seller"]}
        bid.requirements = [requirement]
        assert TradingPartnersRequirement.is_satisfied(offer, bid, requirement) is True
        offer.seller_id = "seller1"
        offer.seller_origin_id = "seller"
        # still should pass
        assert TradingPartnersRequirement.is_satisfied(offer, bid, requirement) is True

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

    @patch("d3a.models.market.market_validators.TradingPartnersRequirement.is_satisfied",
           MagicMock())
    def test_requirements_validator(self, offer, bid):
        # Empty requirement, should be satisfied
        offer.requirements = [{}]
        assert RequirementsSatisfiedChecker.is_satisfied(offer, bid) is True

        offer.requirements = [{"trading_partners": ["x"]}]
        RequirementsSatisfiedChecker.is_satisfied(offer, bid)
        TradingPartnersRequirement.is_satisfied.assert_called_once()
