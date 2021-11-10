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
import uuid

from gsy_framework.constants_limits import ConstSettings
import pytest

from gsy_e.models.strategy.external_strategies.load import LoadHoursExternalStrategy
from tests.strategies.external.utils import (
    assert_bid_offer_aggregator_commands_return_value,
    check_external_command_endpoint_with_correct_payload_succeeds,
    create_areas_markets_for_strategy_fixture)


@pytest.fixture(name="external_load")
def external_load_fixture():
    ConstSettings.IAASettings.MARKET_TYPE = 2
    yield create_areas_markets_for_strategy_fixture(LoadHoursExternalStrategy(100))
    ConstSettings.IAASettings.MARKET_TYPE = 1


class TestLoadForecastExternalStrategy:

    @staticmethod
    def test_bid_succeeds(external_load):
        arguments = {"price": 1, "energy": 2}
        check_external_command_endpoint_with_correct_payload_succeeds(external_load,
                                                                      "bid", arguments)

    @staticmethod
    def test_list_bids_succeeds(external_load):
        check_external_command_endpoint_with_correct_payload_succeeds(external_load,
                                                                      "list_bids", {})

    @staticmethod
    def test_delete_bid_succeeds(external_load):
        check_external_command_endpoint_with_correct_payload_succeeds(external_load,
                                                                      "delete_bid", {})

    @staticmethod
    def test_bid_aggregator(external_load):
        external_load.state._energy_requirement_Wh[
            external_load.spot_market.time_slot] = 1000.0
        return_value = external_load.trigger_aggregator_commands(
            {
                "type": "bid",
                "price": 200.0,
                "energy": 0.5,
                "transaction_id": str(uuid.uuid4())
            }
        )
        assert_bid_offer_aggregator_commands_return_value(return_value, False)

    @staticmethod
    def test_delete_bid_aggregator(external_load):
        bid = external_load.post_bid(external_load.spot_market, 200.0, 1.0)

        return_value = external_load.trigger_aggregator_commands(
            {
                "type": "delete_bid",
                "bid": str(bid.id),
                "transaction_id": str(uuid.uuid4())
            }
        )
        assert return_value["status"] == "ready"
        assert return_value["command"] == "bid_delete"
        assert return_value["deleted_bids"] == [bid.id]

    @staticmethod
    def test_list_bids_aggregator(external_load):
        bid = external_load.post_bid(external_load.spot_market, 200.0, 1.0)

        return_value = external_load.trigger_aggregator_commands(
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
