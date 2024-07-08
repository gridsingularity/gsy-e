from unittest.mock import MagicMock, call

import pendulum
import pytest
from gsy_framework.enums import AvailableMarketTypes

from gsy_e.models.area import Area
from gsy_e.models.strategy.energy_parameters.energy_params_eb import (
    ConsumptionStandardProfileEnergyParameters, ProductionStandardProfileEnergyParameters)
from gsy_e.models.strategy.load_hours import LoadHoursStrategy
from gsy_e.models.strategy.pv import PVStrategy


@pytest.fixture(name="load")
def load_fixture():
    """Load asset."""
    return Area(
        "Load",
        strategy=LoadHoursStrategy(
            avg_power_W=200,
            hrs_of_day=list(range(12, 18)),
            final_buying_rate=35,
        ),
    )


@pytest.mark.slow
class TestConsumptionStandardProfileEnergyParameters:
    """Tests for the ConsumptionStandardProfileEnergyParameters class."""

    @staticmethod
    def test_event_traded_energy(load):
        energy_params = ConsumptionStandardProfileEnergyParameters(capacity_kW=200)
        state_mock = MagicMock()
        energy_params._state = state_mock  # pylint: disable=protected-access
        # We call this method to set the area and the profile generator
        energy_params.event_activate_energy(load)

        market_slot = pendulum.datetime(2022, 2, 1, 12, 0)
        product_type = AvailableMarketTypes.DAY_FORWARD
        energy_params.event_traded_energy(
            energy_kWh=50,
            market_slot=market_slot,
            product_type=product_type)

        assert state_mock.decrement_energy_requirement.call_count == 4

        area_name = "Load"
        # We want to make sure that all the expected calls to the state class are correctly issued
        calls = [
            call(purchased_energy_Wh=50000, area_name=area_name,
                 time_slot=pendulum.datetime(2022, 2, 1, 12, 0)),
            call(purchased_energy_Wh=50000, area_name=area_name,
                 time_slot=pendulum.datetime(2022, 2, 1, 12, 15)),
            call(purchased_energy_Wh=50000, area_name=area_name,
                 time_slot=pendulum.datetime(2022, 2, 1, 12, 30)),
            call(purchased_energy_Wh=50000, area_name=area_name,
                 time_slot=pendulum.datetime(2022, 2, 1, 12, 45)),
        ]

        state_mock.decrement_energy_requirement.assert_has_calls(calls)


@pytest.fixture(name="pv")
def pv_fixture():
    """PV asset."""
    return Area(
        "PV", strategy=PVStrategy(2, 80)
    )


@pytest.mark.slow
class TestProductionStandardProfileEnergyParameters:
    """Tests for the ConsumptionStandardProfileEnergyParameters class."""

    @staticmethod
    def test_event_traded_energy(pv):
        energy_params = ProductionStandardProfileEnergyParameters(capacity_kW=200)
        state_mock = MagicMock()
        energy_params._state = state_mock  # pylint: disable=protected-access
        # We call this method to set the area and the profile generator
        energy_params.event_activate_energy(pv)

        market_slot = pendulum.datetime(2022, 2, 1, 12, 0)
        product_type = AvailableMarketTypes.DAY_FORWARD
        energy_params.event_traded_energy(
            energy_kWh=50,
            market_slot=market_slot,
            product_type=product_type)

        assert state_mock.decrement_available_energy.call_count == 4

        area_name = "PV"
        # We want to make sure that all the expected calls to the state class are correctly issued
        calls = [
            call(sold_energy_kWh=50, area_name=area_name,
                 time_slot=pendulum.datetime(2022, 2, 1, 12, 0)),
            call(sold_energy_kWh=50, area_name=area_name,
                 time_slot=pendulum.datetime(2022, 2, 1, 12, 15)),
            call(sold_energy_kWh=50, area_name=area_name,
                 time_slot=pendulum.datetime(2022, 2, 1, 12, 30)),
            call(sold_energy_kWh=50, area_name=area_name,
                 time_slot=pendulum.datetime(2022, 2, 1, 12, 45))
        ]

        state_mock.decrement_available_energy.assert_has_calls(calls)
