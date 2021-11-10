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

import pytest

from gsy_e.models.strategy.external_strategies.storage import StorageExternalStrategy
from tests.strategies.external.utils import (
    check_external_command_endpoint_with_correct_payload_succeeds,
    create_areas_markets_for_strategy_fixture)


@pytest.fixture(name="external_storage")
def external_storage_fixture():
    return create_areas_markets_for_strategy_fixture(StorageExternalStrategy())


class TestPVForecastExternalStrategy:

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
