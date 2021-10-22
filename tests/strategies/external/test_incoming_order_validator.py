"""Test module for order validators used in external strategies."""

import pytest
from d3a.models.strategy.external_strategies.order_validators import (
    DegreesOfFreedomValidator, OrderValidationWarning)


@pytest.fixture(name="order_with_dof")
def order_with_dof_fixture():
    """Return an example of a valid order with DoF (attributes and requirements)."""
    return {
        "type": "bid", "energy": 0.025, "price": 30, "replace_existing": True,
        "attributes": {"energy_type": "PV"}, "requirements": [{"price": 12}],
        "timeslot": None, "transaction_id": "4f676895-32b5-42ce-9f7b-8c54a8f8b64f"}


@pytest.fixture(name="order_without_dof")
def order_without_dof_fixture():
    """Return an example of a valid order with DoF (attributes and requirements)."""
    return {
        "type": "bid", "energy": 0.025, "price": 30, "replace_existing": True,
        "attributes": None, "requirements": None,
        "timeslot": None, "transaction_id": "4f676895-32b5-42ce-9f7b-8c54a8f8b64f"}


class TestDegreesOfFreedomValidator:
    """Tests for the DegreesOfFreedomValidator class."""

    @staticmethod
    @pytest.mark.parametrize("order", ["order_with_dof", "order_without_dof"])
    def test_validate_succeeds_with_order_with_dof_if_enabled(order, request):
        """The validation succeeds if DoF are enabled."""
        validator = DegreesOfFreedomValidator(accept_degrees_of_freedom=True)
        order = request.getfixturevalue(order)
        validator.validate(order)  # The validation is successful with no exceptions

    @staticmethod
    def test_validate_succeeds_with_order_without_dof_if_disabled(order_without_dof):
        """The validation succeeds if DoF are disabled and the order does not contain them."""
        validator = DegreesOfFreedomValidator(accept_degrees_of_freedom=False)
        validator.validate(order_without_dof)  # The validation is successful with no exceptions

    @staticmethod
    def test_validate_raises_warning_with_order_with_dof_if_disabled(order_with_dof):
        """The validation fails when DoF are disabled but the order contains them."""
        validator = DegreesOfFreedomValidator(accept_degrees_of_freedom=False)
        with pytest.raises(OrderValidationWarning):
            validator.validate(order_with_dof)
