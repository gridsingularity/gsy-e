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
import json
import uuid

import pytest
from gsy_framework.constants_limits import DATE_TIME_FORMAT, ConstSettings

from gsy_e.models.strategy.external_strategies.storage import StorageExternalStrategy
# pylint: disable=unused-import
from tests.strategies.external.fixtures import future_market_fixture  # noqa
from tests.strategies.external.utils import (
    assert_bid_offer_aggregator_commands_return_value,
    check_external_command_endpoint_with_correct_payload_succeeds,
    create_areas_markets_for_strategy_fixture)

# pylint: disable=missing-function-docstring


@pytest.fixture(name="external_storage")
def external_storage_fixture():
    """Create a StorageExternalStrategy instance in a two-sided market."""
    ConstSettings.MASettings.MARKET_TYPE = 2
    yield create_areas_markets_for_strategy_fixture(StorageExternalStrategy())
    ConstSettings.MASettings.MARKET_TYPE = 1


class TestStorageExternalStrategy:
    """Tests for the StorageExternalStrategy class."""
    # pylint: disable=protected-access

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
    def test_bid_aggregator_post_bid_succeeds(external_storage):
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
    def test_bid_aggregator_post_bid_with_more_than_desired_energy_fails(external_storage):
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
    @pytest.mark.skip("Attributes / requirements feature disabled.")
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
    def test_bid_aggregator_post_future_bid_succeeds(external_storage, future_markets):
        future_energy_kWh = 0.2
        external_storage.area._markets.future_markets = future_markets

        for time_slot in future_markets.market_time_slots:
            external_storage.state.energy_to_buy_dict[time_slot] = future_energy_kWh
            external_storage.state.offered_buy_kWh[time_slot] = 0.1
            external_storage.state.pledged_buy_kWh[time_slot] = 0.1
            return_value = external_storage.trigger_aggregator_commands(
                {
                    "type": "bid",
                    "price": 200.0,
                    "energy": future_energy_kWh,
                    "time_slot": time_slot.format(DATE_TIME_FORMAT),
                    "transaction_id": str(uuid.uuid4())
                }
            )
            assert return_value["status"] == "ready"
            bid_id = json.loads(return_value["bid"])["id"]
            assert future_markets.bids[bid_id].energy == future_energy_kWh
        assert len(future_markets.bids.values()) == len(future_markets.market_time_slots)

    @staticmethod
    def test_bid_aggregator_post_future_bid_more_than_required_energy_fails(
            external_storage, future_markets):
        future_energy_kWh = 0.4
        external_storage.area._markets.future_markets = future_markets

        for time_slot in future_markets.market_time_slots:
            external_storage.state.energy_to_buy_dict[time_slot] = 0.2
            external_storage.state.offered_buy_kWh[time_slot] = 0.1
            external_storage.state.pledged_buy_kWh[time_slot] = 0.1
            return_value = external_storage.trigger_aggregator_commands(
                {
                    "type": "bid",
                    "price": 200.0,
                    "energy": future_energy_kWh,
                    "time_slot": time_slot.format(DATE_TIME_FORMAT),
                    "transaction_id": str(uuid.uuid4())
                }
            )

            assert return_value["status"] == "error"
            assert len(future_markets.offers.values()) == 0

    @staticmethod
    def test_offer_aggregator_post_offer_succeeds(external_storage):
        """The _offer_aggregator command succeeds."""
        external_storage.state.energy_to_sell_dict[
            external_storage.spot_market.time_slot] = 1
        return_value = external_storage.trigger_aggregator_commands({
            "type": "offer",
            "price": 200.0,
            "energy": 0.5,
            "transaction_id": str(uuid.uuid4())})

        assert_bid_offer_aggregator_commands_return_value(return_value, True)
        assert return_value["message"] == ""

    @staticmethod
    def test_offer_aggregator_post_offer_more_than_available_energy_fails(external_storage):
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
    @pytest.mark.skip("Attributes / requirements feature disabled.")
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
    def test_offer_aggregator_post_future_offer_succeeds(external_storage, future_markets):
        future_energy_kWh = 0.2
        external_storage.area._markets.future_markets = future_markets

        for time_slot in future_markets.market_time_slots:
            external_storage.state.energy_to_sell_dict[time_slot] = future_energy_kWh
            external_storage.state.offered_sell_kWh[time_slot] = 0.1
            external_storage.state.pledged_sell_kWh[time_slot] = 0.1
            return_value = external_storage.trigger_aggregator_commands(
                {
                    "type": "offer",
                    "price": 200.0,
                    "energy": future_energy_kWh,
                    "time_slot": time_slot.format(DATE_TIME_FORMAT),
                    "transaction_id": str(uuid.uuid4())
                }
            )
            assert return_value["status"] == "ready"
            offer_id = json.loads(return_value["offer"])["id"]
            assert future_markets.offers[offer_id].energy == future_energy_kWh
        assert len(future_markets.offers.values()) == len(future_markets.market_time_slots)

    @staticmethod
    def test_offer_aggregator_post_future_offer_more_than_available_energy_fails(
            external_storage, future_markets):
        future_energy_kWh = 0.4
        external_storage.area._markets.future_markets = future_markets

        for time_slot in future_markets.market_time_slots:
            external_storage.state.energy_to_sell_dict[time_slot] = 0.2
            external_storage.state.offered_sell_kWh[time_slot] = 0.1
            external_storage.state.pledged_sell_kWh[time_slot] = 0.1
            return_value = external_storage.trigger_aggregator_commands(
                {
                    "type": "offer",
                    "price": 200.0,
                    "energy": future_energy_kWh,
                    "time_slot": time_slot.format(DATE_TIME_FORMAT),
                    "transaction_id": str(uuid.uuid4())
                }
            )

            assert return_value["status"] == "error"
            assert len(future_markets.offers.values()) == 0
