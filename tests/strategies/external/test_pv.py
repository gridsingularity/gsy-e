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
# pylint: disable=missing-function-docstring, protected-access, missing-class-docstring
# pylint: disable=unused-import
import uuid

import pytest
from gsy_framework.constants_limits import DATE_TIME_FORMAT

from gsy_e.models.strategy.external_strategies.pv import PVExternalStrategy
from tests.strategies.external.fixtures import future_market_fixture  # noqa
from tests.strategies.external.fixtures import settlement_market_fixture  # noqa
from tests.strategies.external.utils import (
    assert_bid_offer_aggregator_commands_return_value,
    check_external_command_endpoint_with_correct_payload_succeeds,
    create_areas_markets_for_strategy_fixture)


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
    def test_bid_aggregator_can_not_place_bid_to_spot_market(external_pv):
        return_value = external_pv.trigger_aggregator_commands(
            {
                "type": "bid",
                "price": 200.0,
                "energy": 0.5,
                "transaction_id": str(uuid.uuid4())
            }
        )
        assert return_value["status"] == "error"
        assert "Bid not supported for PV on spot markets." in return_value["error_message"]

    @staticmethod
    def test_bid_aggregator_places_settlement_bid(external_pv, settlement_market):
        unsettled_energy_kWh = 0.5
        external_pv.area._markets.settlement_market_ids = [settlement_market.id]
        external_pv.area._markets.settlement_markets = {
            settlement_market.time_slot: settlement_market}
        external_pv.state._forecast_measurement_deviation_kWh[settlement_market.time_slot] = (
            unsettled_energy_kWh)
        external_pv.state._unsettled_deviation_kWh[settlement_market.time_slot] = (
            unsettled_energy_kWh)
        return_value = external_pv.trigger_aggregator_commands(
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
    def test_offer_aggregator_places_settlement_offer(external_pv, settlement_market):
        unsettled_energy_kWh = 0.5
        external_pv.area._markets.settlement_market_ids = [settlement_market.id]
        external_pv.area._markets.settlement_markets = {
            settlement_market.time_slot: settlement_market}
        external_pv.state._forecast_measurement_deviation_kWh[settlement_market.time_slot] = (
            -1 * unsettled_energy_kWh)
        external_pv.state._unsettled_deviation_kWh[settlement_market.time_slot] = (
            unsettled_energy_kWh)
        return_value = external_pv.trigger_aggregator_commands(
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
    def test_offer_aggregator_places_future_offer(external_pv, future_markets):
        future_energy_kWh = 0.5
        external_pv.area._markets.future_markets = future_markets

        for time_slot in future_markets.market_time_slots:
            external_pv.state._available_energy_kWh[time_slot] = future_energy_kWh
            return_value = external_pv.trigger_aggregator_commands(
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
    def test_offer_aggregator_succeeds_with_warning_if_dof_are_disabled(external_pv):
        """
        The _offer_aggregator command succeeds, but it shows a warning if Degrees of Freedom are
        disabled and nevertheless provided.
        """
        external_pv.simulation_config.enable_degrees_of_freedom = False
        external_pv.state._available_energy_kWh[external_pv.spot_market.time_slot] = 1.0
        return_value = external_pv.trigger_aggregator_commands(
            {
                "type": "offer",
                "price": 200.0,
                "energy": 0.5,
                "attributes": {"energy_type": "Green"},
                "requirements": [{"price": 12}],
                "transaction_id": str(uuid.uuid4())
            }
        )
        assert_bid_offer_aggregator_commands_return_value(return_value, True)
        assert return_value["message"] == (
            "The following arguments are not supported for this market and have been removed from "
            "your order: ['requirements', 'attributes'].")

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
    def test_delete_offer_aggregator_deletes_offer_from_future_market(external_pv, future_markets):
        external_pv.area._markets.future_markets = future_markets
        for time_slot in future_markets.market_time_slots:
            offer = external_pv.post_offer(
                external_pv.area.future_markets, False, price=200.0, energy=1.0,
                time_slot=time_slot)

            return_value = external_pv.trigger_aggregator_commands(
                {
                    "type": "delete_offer",
                    "offer": str(offer.id),
                    "transaction_id": str(uuid.uuid4()),
                    "time_slot": time_slot.format(DATE_TIME_FORMAT)
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
