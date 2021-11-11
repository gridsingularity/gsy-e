"""Test the module for the Degrees of Freedom filter used in external strategies."""

from typing import Dict

import pytest

from gsy_e.models.strategy.external_strategies.dof_filter import DegreesOfFreedomFilter


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


class TestDegreesOfFreedomFilter:
    """Tests for the DegreesOfFreedomFilter class."""

    @staticmethod
    def test_filter_succeeds_with_order_with_dof(order_with_dof: Dict):
        """The validation succeeds if DoF are enabled."""
        filtered_order, filtered_fields = DegreesOfFreedomFilter.apply(order_with_dof)
        expected_order = {
            "type": "bid", "energy": 0.025, "price": 30, "replace_existing": True,
            "timeslot": None, "transaction_id": "4f676895-32b5-42ce-9f7b-8c54a8f8b64f"}

        assert filtered_order == expected_order
        assert filtered_fields == ["requirements", "attributes"]

    @staticmethod
    def test_filter_succeeds_with_order_without_dof(order_without_dof: Dict):
        """The validation succeeds if DoF are disabled and the order does not contain them."""
        filtered_order, filtered_fields = DegreesOfFreedomFilter.apply(order_without_dof)

        assert filtered_order == order_without_dof
        assert filtered_fields == []
