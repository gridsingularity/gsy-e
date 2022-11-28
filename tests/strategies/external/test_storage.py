"""
Copyright 2018 Grid Singularity
This file is part of Grid Singularity Exchange.

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
# pylint: disable=missing-function-docstring

import uuid

import pytest
from gsy_framework.constants_limits import ConstSettings

from gsy_e.models.strategy.external_strategies.storage import StorageExternalStrategy
from tests.strategies.external.fixtures import (future_market_fixture,  # noqa
                                                settlement_market_fixture)
from tests.strategies.external.utils import (
    assert_bid_offer_aggregator_commands_return_value,
    check_external_command_endpoint_with_correct_payload_succeeds,
    create_areas_markets_for_strategy_fixture)


@pytest.fixture(name="external_storage")
def external_storage_fixture():
    """Create a StorageExternalStrategy instance in a two-sided market."""
    ConstSettings.MASettings.MARKET_TYPE = 2
    yield create_areas_markets_for_strategy_fixture(StorageExternalStrategy())
    ConstSettings.MASettings.MARKET_TYPE = 1


class TestStorageExternalStrategy:
    """Tests for the StorageExternalStrategy class."""

    @staticmethod
    def test_offer_succeeds(external_storage):
        arguments = {"price": 1, "energy": 2}
        check_external_command_endpoint_with_correct_payload_succeeds(
            external_storage, "offer", arguments)

    @staticmethod
    def test_list_offers_succeeds(external_storage):
        check_external_command_endpoint_with_correct_payload_succeeds(
            external_storage, "list_offers", {})

    @staticmethod
    def test_delete_offer_succeeds(external_storage):
        check_external_command_endpoint_with_correct_payload_succeeds(
            external_storage, "delete_offer", {})

    @staticmethod
    def test_bid_succeeds(external_storage):
        arguments = {"price": 1, "energy": 2}
        check_external_command_endpoint_with_correct_payload_succeeds(
            external_storage, "bid", arguments)

    @staticmethod
    def test_list_bids_succeeds(external_storage):
        check_external_command_endpoint_with_correct_payload_succeeds(
            external_storage, "list_bids", {})

    @staticmethod
    def test_delete_bid_succeeds(external_storage):
        check_external_command_endpoint_with_correct_payload_succeeds(
            external_storage, "delete_bid", {})

    # Aggregator tests
    @staticmethod
    def test_bid_aggregator(external_storage):
        """The _bid_aggregator command succeeds."""
        external_storage.state.energy_to_buy_dict[
            external_storage.spot_market.time_slot] = 1
        return_value = external_storage.trigger_aggregator_commands({
            "type": "bid",
            "price": 200.0,
            "energy": 0.5,
            "attributes": {"energy_type": "Green"},
            "requirements": [{"price": 12}],
            "transaction_id": str(uuid.uuid4())})

        assert_bid_offer_aggregator_commands_return_value(return_value, False)
        assert return_value["message"] == ""

    @staticmethod
    def test_bid_aggregator_fails_to_place_bid_more_than_desired_energy(external_storage):
        external_storage.state.energy_to_buy_dict[
            external_storage.spot_market.time_slot] = 1
        return_value = external_storage.trigger_aggregator_commands({
            "type": "bid",
            "price": 200.0,
            "energy": 2,
            "attributes": {"energy_type": "Green"},
            "requirements": [{"price": 12}],
            "transaction_id": str(uuid.uuid4())})

        assert return_value["status"] == "error"

    @staticmethod
    def test_bid_aggregator_succeeds_with_warning_if_dof_are_disabled(external_storage):
        """
        The _bid_aggregator command succeeds, but it shows a warning if Degrees of Freedom are
        disabled and nevertheless provided.
        """
        external_storage.simulation_config.enable_degrees_of_freedom = False
        external_storage.state.energy_to_buy_dict[
            external_storage.spot_market.time_slot] = 1000.0
        return_value = external_storage.trigger_aggregator_commands({
            "type": "bid",
            "price": 200.0,
            "energy": 0.5,
            "attributes": {"energy_type": "PV"},
            "requirements": [{"price": 12}],
            "transaction_id": str(uuid.uuid4())})

        assert_bid_offer_aggregator_commands_return_value(return_value, False)
        assert return_value["message"] == (
            "The following arguments are not supported for this market and have been removed from "
            "your order: ['requirements', 'attributes'].")

    @staticmethod
    def test_bid_aggregator_places_settlement_bid(external_storage, settlement_market):
        unsettled_energy_kWh = 0.2
        external_storage.area._markets.settlement_market_ids = [settlement_market.id]
        external_storage.area._markets.settlement_markets = {
            settlement_market.time_slot: settlement_market}
        external_storage.state.energy_to_buy_dict[
            settlement_market.time_slot] = unsettled_energy_kWh
        external_storage.state.pledged_buy_kWh[settlement_market.time_slot] = 0.1
        external_storage.state.offered_buy_kWh[settlement_market.time_slot] = 0.1

        return_value = external_storage.trigger_aggregator_commands({
            "type": "bid",
            "price": 200,
            "energy": 0.2,
            "time_slot": str(settlement_market.time_slot.naive()),
            "transaction_id": str(uuid.uuid4()),
        })
        assert return_value["status"] == "ready"
        assert len(settlement_market.bids.values()) == 1
        assert list(settlement_market.bids.values())[0].energy == unsettled_energy_kWh

    @staticmethod
    def test_bid_aggregator_fails_placing_settlement_bid_more_than_required_energy(
            external_storage, settlement_market):
        unsettled_energy_kWh = 0.2
        external_storage.area._markets.settlement_market_ids = [settlement_market.id]
        external_storage.area._markets.settlement_markets = {
            settlement_market.time_slot: settlement_market}
        external_storage.state.energy_to_buy_dict[
            settlement_market.time_slot] = unsettled_energy_kWh
        external_storage.state.pledged_buy_kWh[settlement_market.time_slot] = 0.1
        external_storage.state.offered_buy_kWh[settlement_market.time_slot] = 0.1

        return_value = external_storage.trigger_aggregator_commands({
            "type": "bid",
            "price": 200,
            "energy": 0.4,
            "time_slot": str(settlement_market.time_slot.naive()),
            "transaction_id": str(uuid.uuid4()),
        })
        assert return_value["status"] == "error"
        assert len(settlement_market.bids.values()) == 0

    @staticmethod
    def test_offer_aggregator(external_storage):
        """The _offer_aggregator command succeeds."""
        external_storage.state.energy_to_sell_dict[
            external_storage.spot_market.time_slot] = 1
        return_value = external_storage.trigger_aggregator_commands({
            "type": "offer",
            "price": 200.0,
            "energy": 0.5,
            "attributes": {"energy_type": "Green"},
            "requirements": [{"price": 12}],
            "transaction_id": str(uuid.uuid4())})

        assert_bid_offer_aggregator_commands_return_value(return_value, True)
        assert return_value["message"] == ""

    @staticmethod
    def test_offer_aggregator_fails_to_place_bid_more_than_available_energy(external_storage):
        external_storage.state.energy_to_sell_dict[
            external_storage.spot_market.time_slot] = 1
        return_value = external_storage.trigger_aggregator_commands({
            "type": "offer",
            "price": 200.0,
            "energy": 2,
            "attributes": {"energy_type": "Green"},
            "requirements": [{"price": 12}],
            "transaction_id": str(uuid.uuid4())})

        assert return_value["status"] == "error"

    @staticmethod
    def test_offer_aggregator_succeeds_with_warning_if_dof_are_disabled(external_storage):
        """
        The _offer_aggregator command succeeds, but it shows a warning if Degrees of Freedom are
        disabled and nevertheless provided.
        """
        external_storage.simulation_config.enable_degrees_of_freedom = False
        external_storage.state.energy_to_sell_dict[
            external_storage.spot_market.time_slot] = 1
        return_value = external_storage.trigger_aggregator_commands({
            "type": "offer",
            "price": 200.0,
            "energy": 0.5,
            "attributes": {"energy_type": "Green"},
            "requirements": [{"price": 12}],
            "transaction_id": str(uuid.uuid4())})

        assert_bid_offer_aggregator_commands_return_value(return_value, True)
        assert return_value["message"] == (
            "The following arguments are not supported for this market and have been removed from "
            "your order: ['requirements', 'attributes'].")

    @staticmethod
    def test_offer_aggregator_places_settlement_offer(external_storage, settlement_market):
        unsettled_energy_kWh = 0.2
        external_storage.area._markets.settlement_market_ids = [settlement_market.id]
        external_storage.area._markets.settlement_markets = {
            settlement_market.time_slot: settlement_market}
        external_storage.state.energy_to_sell_dict[
            settlement_market.time_slot] = unsettled_energy_kWh
        external_storage.state.offered_sell_kWh[settlement_market.time_slot] = 0.1
        external_storage.state.pledged_sell_kWh[settlement_market.time_slot] = 0.1

        return_value = external_storage.trigger_aggregator_commands({
            "type": "offer",
            "price": 200,
            "energy": 0.2,
            "time_slot": str(settlement_market.time_slot.naive()),
            "transaction_id": str(uuid.uuid4()),
        })
        assert return_value["status"] == "ready"
        assert len(settlement_market.offers.values()) == 1
        assert list(settlement_market.offers.values())[0].energy == unsettled_energy_kWh

    @staticmethod
    def test_offer_aggregator_fails_placing_settlement_offer_more_than_avaialble_energy(
            external_storage, settlement_market):
        unsettled_energy_kWh = 0.2
        external_storage.area._markets.settlement_market_ids = [settlement_market.id]
        external_storage.area._markets.settlement_markets = {
            settlement_market.time_slot: settlement_market}
        external_storage.state.energy_to_sell_dict[
            settlement_market.time_slot] = unsettled_energy_kWh
        external_storage.state.offered_sell_kWh[settlement_market.time_slot] = 0.1
        external_storage.state.pledged_sell_kWh[settlement_market.time_slot] = 0.1

        return_value = external_storage.trigger_aggregator_commands({
            "type": "offer",
            "price": 200,
            "energy": 0.4,
            "time_slot": str(settlement_market.time_slot.naive()),
            "transaction_id": str(uuid.uuid4()),
        })
        assert return_value["status"] == "error"
        assert len(settlement_market.offers.values()) == 0
