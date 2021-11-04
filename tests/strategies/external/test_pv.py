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
import uuid

import pytest

from d3a.models.strategy.external_strategies.pv import PVExternalStrategy
from tests.strategies.external.utils import (
    check_external_command_endpoint_with_correct_payload_succeeds,
    create_areas_markets_for_strategy_fixture, assert_bid_offer_aggregator_commands_return_value)


@pytest.fixture(name="external_pv")
def external_pv_fixture():
    return create_areas_markets_for_strategy_fixture(PVExternalStrategy())


class TestPVForecastExternalStrategy:

    @staticmethod
    def test_offer_succeeds(external_pv):
        arguments = {"price": 1, "energy": 2}
        check_external_command_endpoint_with_correct_payload_succeeds(
            external_pv, "offer", arguments)

    @staticmethod
    def test_list_offers_succeeds(external_pv):
        check_external_command_endpoint_with_correct_payload_succeeds(
            external_pv, "list_offers", {})

    @staticmethod
    def test_delete_offer_succeeds(external_pv):
        check_external_command_endpoint_with_correct_payload_succeeds(
            external_pv, "delete_offer", {})

    @staticmethod
    def test_offer_aggregator(external_pv):
        external_pv.state._available_energy_kWh[external_pv.spot_market.time_slot] = 1.0
        return_value = external_pv.trigger_aggregator_commands(
            {
                "type": "offer",
                "price": 200.0,
                "energy": 0.5,
                "transaction_id": str(uuid.uuid4())
            }
        )
        assert_bid_offer_aggregator_commands_return_value(return_value, True)

    @staticmethod
    def test_delete_offer_aggregator(external_pv):
        offer = external_pv.post_offer(
            external_pv.spot_market, False, price=200.0, energy=1.0)
        return_value = external_pv.trigger_aggregator_commands(
            {
                "type": "delete_offer",
                "offer": str(offer.id),
                "transaction_id": str(uuid.uuid4())
            }
        )
        assert return_value["status"] == "ready"
        assert return_value["command"] == "offer_delete"
        assert return_value["deleted_offers"] == [offer.id]

    @staticmethod
    def test_list_offers_aggregator(external_pv):
        offer = external_pv.post_offer(
            external_pv.spot_market, False, price=200.0, energy=1.0)

        return_value = external_pv.trigger_aggregator_commands(
            {
                "type": "list_offers",
                "transaction_id": str(uuid.uuid4())
            }
        )
        assert return_value["status"] == "ready"
        assert return_value["command"] == "list_offers"
        assert return_value["offer_list"] == [
            {"id": offer.id, "price": offer.price, "energy": offer.energy}
        ]
