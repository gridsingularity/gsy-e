# pylint: disable=protected-access, disable=missing-function-docstring, missing-class-docstring
# pylint: disable=too-many-public-methods, unused-import
import json
import uuid

import pytest
from gsy_framework.constants_limits import DATE_TIME_FORMAT, ConstSettings

from gsy_e.models.strategy.external_strategies.smart_meter import SmartMeterExternalStrategy
from tests.strategies.external.fixtures import future_market_fixture  # noqa
from tests.strategies.external.fixtures import settlement_market_fixture  # noqa
from tests.strategies.external.utils import (
    assert_bid_offer_aggregator_commands_return_value,
    check_external_command_endpoint_with_correct_payload_succeeds,
    create_areas_markets_for_strategy_fixture)


@pytest.fixture(name="external_smart_meter")
def external_smart_meter_fixture():
    """Create a SmartMeterExternalStrategy instance in a two-sided market."""
    ConstSettings.MASettings.MARKET_TYPE = 2
    yield create_areas_markets_for_strategy_fixture(SmartMeterExternalStrategy(
        smart_meter_profile={
            "2022-01-01T00:00": 0
        }
    ))
    ConstSettings.MASettings.MARKET_TYPE = 1


class TestSmartMeterExternalStrategy:
    """Tests for the SmartMeterExternalStrategy class."""

    # BID FUNCTIONALITIES #

    @staticmethod
    def test_bid_succeeds(external_smart_meter: SmartMeterExternalStrategy):
        arguments = {"price": 1, "energy": 2}
        check_external_command_endpoint_with_correct_payload_succeeds(
            external_smart_meter, "bid", arguments)

    @staticmethod
    def test_list_bids_succeeds(external_smart_meter: SmartMeterExternalStrategy):
        check_external_command_endpoint_with_correct_payload_succeeds(
            external_smart_meter, "list_bids", {})

    @staticmethod
    def test_delete_bid_succeeds(external_smart_meter: SmartMeterExternalStrategy):
        check_external_command_endpoint_with_correct_payload_succeeds(
            external_smart_meter, "delete_bid", {})

    @staticmethod
    def test_bid_aggregator(external_smart_meter: SmartMeterExternalStrategy):
        external_smart_meter.state.set_desired_energy(
            500.0, external_smart_meter.spot_market.time_slot, overwrite=True)
        return_value = external_smart_meter.trigger_aggregator_commands({
            "type": "bid",
            "price": 200.0,
            "energy": 0.5,
            "transaction_id": str(uuid.uuid4())
        })
        assert_bid_offer_aggregator_commands_return_value(return_value, is_offer=False)

    @staticmethod
    def test_bid_aggregator_fails_to_place_bid_more_than_desired_energy(
        external_smart_meter: SmartMeterExternalStrategy
    ):
        external_smart_meter.state.set_desired_energy(
            500.0, external_smart_meter.spot_market.time_slot, overwrite=True)
        return_value = external_smart_meter.trigger_aggregator_commands({
            "type": "bid",
            "price": 200.0,
            "energy": 0.6,
            "transaction_id": str(uuid.uuid4())
        })
        assert return_value["status"] == "error"

    @staticmethod
    def test_bid_aggregator_places_settlement_bid(
            external_smart_meter: SmartMeterExternalStrategy, settlement_market):
        unsettled_energy_kWh = 0.2
        external_smart_meter.area._markets.settlement_market_ids = [settlement_market.id]
        external_smart_meter.area._markets.settlement_markets = {
            settlement_market.time_slot: settlement_market}
        external_smart_meter.state._forecast_measurement_deviation_kWh[
            settlement_market.time_slot] = (unsettled_energy_kWh)
        external_smart_meter.state._unsettled_deviation_kWh[settlement_market.time_slot] = (
            unsettled_energy_kWh)
        return_value = external_smart_meter.trigger_aggregator_commands({
            "type": "bid",
            "price": 200,
            "energy": 0.2,
            "time_slot": settlement_market.time_slot.format(DATE_TIME_FORMAT),
            "transaction_id": str(uuid.uuid4())
        })
        assert return_value["status"] == "ready"
        assert len(settlement_market.bids.values()) == 1
        assert list(settlement_market.bids.values())[0].energy == unsettled_energy_kWh

    @staticmethod
    def test_bid_aggregator_places_future_bid(external_smart_meter, future_markets):
        future_energy_kWh = 0.5
        external_smart_meter.area._markets.future_markets = future_markets

        for time_slot in future_markets.market_time_slots:
            external_smart_meter.state._energy_requirement_Wh[time_slot] = future_energy_kWh * 1000
            return_value = external_smart_meter.trigger_aggregator_commands(
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
    def test_bid_aggregator_succeeds_with_warning_if_dof_are_disabled(
            external_smart_meter: SmartMeterExternalStrategy):
        """
        The bid_aggregator command succeeds, but it shows a warning if Degrees of Freedom are
        disabled and nevertheless provided.
        """
        external_smart_meter.simulation_config.enable_degrees_of_freedom = False
        external_smart_meter.state.set_desired_energy(
            1000, external_smart_meter.spot_market.time_slot, overwrite=True)
        return_value = external_smart_meter.trigger_aggregator_commands({
            "type": "bid",
            "price": 200,
            "energy": 0.5,
            "attributes": {"energy_type": "PV"},
            "requirements": [{"price": 12}],
            "transaction_id": str(uuid.uuid4())
        })
        assert_bid_offer_aggregator_commands_return_value(return_value, is_offer=False)
        assert return_value["message"] == (
            "The following arguments are not supported for this market and have been removed from "
            "your order: ['requirements', 'attributes'].")

    @staticmethod
    def test_delete_bid_aggregator(external_smart_meter: SmartMeterExternalStrategy):
        bid = external_smart_meter.post_bid(external_smart_meter.spot_market, 200.0, 1.0)
        return_value = external_smart_meter.trigger_aggregator_commands({
            "type": "delete_bid",
            "bid": str(bid.id),
            "transaction_id": str(uuid.uuid4())
        })
        assert return_value["status"] == "ready"
        assert return_value["command"] == "bid_delete"
        assert return_value["deleted_bids"] == [bid.id]

    @staticmethod
    def test_list_bids_aggregator(external_smart_meter: SmartMeterExternalStrategy):
        bid = external_smart_meter.post_bid(external_smart_meter.spot_market, 200.0, 1.0)
        return_value = external_smart_meter.trigger_aggregator_commands({
                "type": "list_bids",
                "transaction_id": str(uuid.uuid4())
        })
        assert return_value["status"] == "ready"
        assert return_value["command"] == "list_bids"
        assert return_value["bid_list"] == [
            {"id": bid.id, "price": bid.price, "energy": bid.energy}]

    # OFFER FUNCTIONALITIES #

    @staticmethod
    def test_offer_succeeds(external_smart_meter: SmartMeterExternalStrategy):
        arguments = {"price": 1, "energy": 2}
        check_external_command_endpoint_with_correct_payload_succeeds(
            external_smart_meter, "offer", arguments)

    @staticmethod
    def test_list_offers_succeeds(external_smart_meter: SmartMeterExternalStrategy):
        check_external_command_endpoint_with_correct_payload_succeeds(
            external_smart_meter, "list_offers", {})

    @staticmethod
    def test_delete_offer_succeeds(external_smart_meter: SmartMeterExternalStrategy):
        check_external_command_endpoint_with_correct_payload_succeeds(
            external_smart_meter, "delete_offer", {})

    @staticmethod
    def test_offer_aggregator(external_smart_meter: SmartMeterExternalStrategy):
        external_smart_meter.state.set_available_energy(
            0.5, external_smart_meter.spot_market.time_slot, overwrite=True)
        return_value = external_smart_meter.trigger_aggregator_commands({
            "type": "offer",
            "price": 200.0,
            "energy": 0.5,
            "transaction_id": str(uuid.uuid4())
        })
        assert_bid_offer_aggregator_commands_return_value(return_value, is_offer=True)

    @staticmethod
    def test_offer_aggregator_fails_to_place_offer_more_than_available_energy(
        external_smart_meter: SmartMeterExternalStrategy
    ):
        external_smart_meter.state.set_available_energy(
            0.5, external_smart_meter.spot_market.time_slot, overwrite=True)
        return_value = external_smart_meter.trigger_aggregator_commands({
            "type": "offer",
            "price": 200.0,
            "energy": 0.6,
            "transaction_id": str(uuid.uuid4())
        })
        assert return_value["status"] == "error"

    @staticmethod
    def test_offer_aggregator_places_settlement_offer(
            external_smart_meter: SmartMeterExternalStrategy, settlement_market):
        unsettled_energy_kWh = 0.5
        external_smart_meter.area._markets.settlement_market_ids = [settlement_market.id]
        external_smart_meter.area._markets.settlement_markets = {
            settlement_market.time_slot: settlement_market}
        external_smart_meter.state._forecast_measurement_deviation_kWh[
            settlement_market.time_slot] = (-1 * unsettled_energy_kWh)
        external_smart_meter.state._unsettled_deviation_kWh[settlement_market.time_slot] = (
            unsettled_energy_kWh)
        return_value = external_smart_meter.trigger_aggregator_commands({
            "type": "offer",
            "price": 200.0,
            "energy": 0.5,
            "time_slot": settlement_market.time_slot.format(DATE_TIME_FORMAT),
            "transaction_id": str(uuid.uuid4())
        })
        assert return_value["status"] == "ready"
        assert len(settlement_market.offers.values()) == 1
        assert list(settlement_market.offers.values())[0].energy == unsettled_energy_kWh

    @staticmethod
    def test_offer_aggregator_places_future_offer(external_smart_meter, future_markets):
        future_energy_kWh = 0.5
        external_smart_meter.area._markets.future_markets = future_markets

        for time_slot in future_markets.market_time_slots:
            external_smart_meter.state._available_energy_kWh[time_slot] = future_energy_kWh
            return_value = external_smart_meter.trigger_aggregator_commands(
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
    def test_offer_aggregator_succeeds_with_warning_if_dof_are_disabled(
            external_smart_meter: SmartMeterExternalStrategy):
        """
        The offer_aggregator command succeeds, but it shows a warning if Degrees of Freedom are
        disabled and nevertheless provided.
        """
        external_smart_meter.simulation_config.enable_degrees_of_freedom = False
        external_smart_meter.state.set_available_energy(
            1.0, external_smart_meter.spot_market.time_slot, overwrite=True)
        return_value = external_smart_meter.trigger_aggregator_commands({
            "type": "offer",
            "price": 200.0,
            "energy": 0.5,
            "attributes": {"energy_type": "Green"},
            "requirements": [{"price": 12}],
            "transaction_id": str(uuid.uuid4())
        })
        assert_bid_offer_aggregator_commands_return_value(return_value, is_offer=True)
        assert return_value["message"] == (
            "The following arguments are not supported for this market and have been removed from "
            "your order: ['requirements', 'attributes'].")

    @staticmethod
    def test_delete_offer_aggregator(external_smart_meter: SmartMeterExternalStrategy):
        offer = external_smart_meter.post_offer(
            external_smart_meter.spot_market, False, price=200.0, energy=1.0)
        return_value = external_smart_meter.trigger_aggregator_commands({
            "type": "delete_offer",
            "offer": str(offer.id),
            "transaction_id": str(uuid.uuid4())
        })
        assert return_value["status"] == "ready"
        assert return_value["command"] == "offer_delete"
        assert return_value["deleted_offers"] == [offer.id]

    @staticmethod
    def test_delete_offer_aggregator_deletes_offer_from_future_market(
            external_smart_meter, future_markets):
        external_smart_meter.area._markets.future_markets = future_markets
        for time_slot in future_markets.market_time_slots:
            offer = external_smart_meter.post_offer(
                external_smart_meter.area.future_markets, False, price=200.0, energy=1.0,
                time_slot=time_slot)

            return_value = external_smart_meter.trigger_aggregator_commands(
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
    def test_delete_bid_aggregator_deletes_bid_from_future_market(
            external_smart_meter, future_markets):
        external_smart_meter.area._markets.future_markets = future_markets
        for time_slot in future_markets.market_time_slots:
            bid = external_smart_meter.post_bid(
                external_smart_meter.area.future_markets, 200.0, 1.0,
                time_slot=time_slot)

            return_value = external_smart_meter.trigger_aggregator_commands(
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
    def test_list_offers_aggregator(external_smart_meter: SmartMeterExternalStrategy):
        offer = external_smart_meter.post_offer(
            external_smart_meter.spot_market, False, price=200.0, energy=1.0)
        return_value = external_smart_meter.trigger_aggregator_commands({
            "type": "list_offers",
            "transaction_id": str(uuid.uuid4())
        })
        assert return_value["status"] == "ready"
        assert return_value["command"] == "list_offers"
        assert return_value["offer_list"] == [
            {"id": offer.id, "price": offer.price, "energy": offer.energy}]
