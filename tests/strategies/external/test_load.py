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
# pylint: disable=missing-function-docstring, protected-access, unused-import
import uuid

import pytest
from gsy_framework.constants_limits import DATE_TIME_FORMAT, ConstSettings

from gsy_e.models.strategy.external_strategies.load import LoadHoursExternalStrategy
from tests.strategies.external.fixtures import future_market_fixture  # noqa
from tests.strategies.external.fixtures import settlement_market_fixture  # noqa
from tests.strategies.external.utils import (
    assert_bid_offer_aggregator_commands_return_value,
    check_external_command_endpoint_with_correct_payload_succeeds,
    create_areas_markets_for_strategy_fixture)


@pytest.fixture(name="external_load")
def external_load_fixture():
    ConstSettings.MASettings.MARKET_TYPE = 2
    yield create_areas_markets_for_strategy_fixture(LoadHoursExternalStrategy(100))
    ConstSettings.MASettings.MARKET_TYPE = 1


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
    def test_offer_aggregator_can_not_place_offer_to_spot_market(external_load):
        return_value = external_load.trigger_aggregator_commands(
            {
                "type": "offer",
                "price": 200.0,
                "energy": 0.5,
                "transaction_id": str(uuid.uuid4())
            }
        )
        assert return_value["status"] == "error"
        assert "Offer not supported for Loads on spot markets." in return_value["error_message"]

    @staticmethod
    def test_bid_aggregator_places_settlement_bid(external_load, settlement_market):
        unsettled_energy_kWh = 0.5
        external_load.area._markets.settlement_market_ids = [settlement_market.id]
        external_load.area._markets.settlement_markets = {
            settlement_market.time_slot: settlement_market}
        external_load.state._forecast_measurement_deviation_kWh[settlement_market.time_slot] = (
            unsettled_energy_kWh)
        external_load.state._unsettled_deviation_kWh[settlement_market.time_slot] = (
            unsettled_energy_kWh)
        return_value = external_load.trigger_aggregator_commands(
            {
                "type": "bid",
                "price": 200.0,
                "energy": unsettled_energy_kWh,
                "time_slot": settlement_market.time_slot.format(DATE_TIME_FORMAT),
                "transaction_id": str(uuid.uuid4())
            }
        )
        assert return_value["status"] == "ready"
        assert len(settlement_market.bids.values()) == 1
        assert list(settlement_market.bids.values())[0].energy == unsettled_energy_kWh

    @staticmethod
    def test_bid_aggregator_places_future_bid(external_load, future_markets):
        future_energy_kWh = 0.5
        external_load.area._markets.future_markets = future_markets

        for time_slot in future_markets.market_time_slots:
            external_load.state._energy_requirement_Wh[time_slot] = future_energy_kWh * 1000
            return_value = external_load.trigger_aggregator_commands(
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
    def test_offer_aggregator_places_settlement_offer(external_load, settlement_market):
        unsettled_energy_kWh = 0.5
        external_load.area._markets.settlement_market_ids = [settlement_market.id]
        external_load.area._markets.settlement_markets = {
            settlement_market.time_slot: settlement_market}
        external_load.state._forecast_measurement_deviation_kWh[settlement_market.time_slot] = (
            -1 * unsettled_energy_kWh)
        external_load.state._unsettled_deviation_kWh[settlement_market.time_slot] = (
            unsettled_energy_kWh)
        return_value = external_load.trigger_aggregator_commands(
            {
                "type": "offer",
                "price": 200.0,
                "energy": unsettled_energy_kWh,
                "time_slot": settlement_market.time_slot.format(DATE_TIME_FORMAT),
                "transaction_id": str(uuid.uuid4())
            }
        )
        assert return_value["status"] == "ready"
        assert len(settlement_market.offers.values()) == 1
        assert list(settlement_market.offers.values())[0].energy == unsettled_energy_kWh

    @staticmethod
    def test_bid_aggregator_succeeds_with_warning_if_dof_are_disabled(external_load):
        """
        The bid_aggregator command succeeds, but it shows a warning if Degrees of Freedom are
        disabled and nevertheless provided.
        """
        external_load.simulation_config.enable_degrees_of_freedom = False
        external_load.state._energy_requirement_Wh[
            external_load.spot_market.time_slot] = 1000.0
        return_value = external_load.trigger_aggregator_commands({
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
    def test_delete_bid_aggregator_deletes_bid_from_future_market(external_load, future_markets):
        external_load.area._markets.future_markets = future_markets
        for time_slot in future_markets.market_time_slots:
            bid = external_load.post_bid(
                external_load.area.future_markets, price=200.0, energy=1.0,
                time_slot=time_slot)

            return_value = external_load.trigger_aggregator_commands(
                {
                    "type": "delete_bid",
                    "offer": str(bid.id),
                    "transaction_id": str(uuid.uuid4()),
                    "time_slot": time_slot.format(DATE_TIME_FORMAT)
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
