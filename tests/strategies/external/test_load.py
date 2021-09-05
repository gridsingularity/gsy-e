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

from d3a.models.strategy.external_strategies.load import LoadHoursExternalStrategy
from tests.strategies.external.utils import (
    check_external_command_endpoint_with_correct_payload_succeeds,
    create_areas_markets_for_strategy_fixture, assert_bid_offer_aggregator_commands_return_value)


@pytest.fixture
def ext_load_fixture():
    from d3a_interface.constants_limits import ConstSettings
    ConstSettings.IAASettings.MARKET_TYPE = 2
    yield create_areas_markets_for_strategy_fixture(LoadHoursExternalStrategy(100))
    ConstSettings.IAASettings.MARKET_TYPE = 1


class TestLoadForecastExternalStrategy:

    def test_bid_succeeds(self, ext_load_fixture):
        arguments = {"price": 1, "energy": 2}
        check_external_command_endpoint_with_correct_payload_succeeds(ext_load_fixture,
                                                                      "bid", arguments)

    def test_list_bids_succeeds(self, ext_load_fixture):
        check_external_command_endpoint_with_correct_payload_succeeds(ext_load_fixture,
                                                                      "list_bids", {})

    def test_delete_bid_succeeds(self, ext_load_fixture):
        check_external_command_endpoint_with_correct_payload_succeeds(ext_load_fixture,
                                                                      "delete_bid", {})

    def test_bid_aggregator(self, ext_load_fixture):
        ext_load_fixture.state._energy_requirement_Wh[
            ext_load_fixture.next_market.time_slot] = 1000.0
        return_value = ext_load_fixture.trigger_aggregator_commands(
            {
                "type": "bid",
                "price": 200.0,
                "energy": 0.5,
                "transaction_id": str(uuid.uuid4())
            }
        )
        assert_bid_offer_aggregator_commands_return_value(return_value, False)

    def test_delete_bid_aggregator(self, ext_load_fixture):
        bid = ext_load_fixture.post_bid(ext_load_fixture.next_market, 200.0, 1.0)

        return_value = ext_load_fixture.trigger_aggregator_commands(
            {
                "type": "delete_bid",
                "bid": str(bid.id),
                "transaction_id": str(uuid.uuid4())
            }
        )
        assert return_value["status"] == "ready"
        assert return_value["command"] == "bid_delete"
        assert return_value["deleted_bids"] == [bid.id]

    def test_list_bids_aggregator(self, ext_load_fixture):
        bid = ext_load_fixture.post_bid(ext_load_fixture.next_market, 200.0, 1.0)

        return_value = ext_load_fixture.trigger_aggregator_commands(
            {
                "type": "list_bids",
                "transaction_id": str(uuid.uuid4())
            }
        )
        assert return_value["status"] == "ready"
        assert return_value["command"] == "list_bids"
        assert return_value["bid_list"] == [
            {"id": bid.id, "price": bid.price, "energy": bid.energy}
        ]
