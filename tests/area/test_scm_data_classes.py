# pylint: disable=protected-access
import logging
from math import isclose
from unittest.mock import Mock

import pytest
from pendulum import datetime

import gsy_e.constants
from gsy_e.models.area.scm_dataclasses import (
    AreaFees,
    FeeContainer,
    AreaEnergyRates,
    HomeAfterMeterData,
    HomeAfterMeterDataWithoutSurplusTrade,
    AreaEnergyBills,
    AreaEnergyBillsWithoutSurplusTrade,
)


@pytest.fixture(name="area_fees")
def fixture_area_fees():
    return AreaFees(
        grid_import_fee_const=0.2,
        grid_export_fee_const=0.1,
        grid_fees_reduction=0.1,
        per_kWh_fees={
            "taxes_surcharges": FeeContainer(value=0.01, price=0.1),
            "other_fee": FeeContainer(value=0.001, price=0.1),
        },
        monthly_fees={
            "monthly_fee": FeeContainer(value=0.002, price=0.2),
            "other_monthly_fee": FeeContainer(value=0.0002, price=0.2),
        },
    )


@pytest.fixture(name="area_energy_rates")
def fixture_energy_rates():
    return AreaEnergyRates(
        area_fees=AreaFees(grid_fees_reduction=0.1, grid_import_fee_const=0.2),
        utility_rate=30,
        intracommunity_base_rate=11,
        feed_in_tariff=7,
    )


@pytest.fixture(name="home_after_meter_data")
def fixture_home_after_meter_data():
    return HomeAfterMeterData(
        home_uuid="uuid",
        home_name="home name",
    )


@pytest.fixture(name="area_energy_bills")
def fixture_area_energy_bills():
    return AreaEnergyBills(
        energy_rates=AreaEnergyRates(
            area_fees=AreaFees(
                grid_import_fee_const=0.2, grid_fees_reduction=0.1, grid_export_fee_const=0.01
            ),
            utility_rate=30,
            intracommunity_base_rate=11,
            feed_in_tariff=7,
        )
    )


@pytest.fixture(name="area_energy_bills_without_surplus_trade")
def fixture_area_energy_bills_without_surplus_trade():
    return AreaEnergyBillsWithoutSurplusTrade(
        energy_rates=AreaEnergyRates(
            area_fees=AreaFees(
                grid_import_fee_const=0.2, grid_fees_reduction=0.1, grid_export_fee_const=0.01
            ),
            utility_rate=30,
            intracommunity_base_rate=11,
            feed_in_tariff=7,
        )
    )


class TestAreaFees:

    @staticmethod
    def test_price_as_dict_returns_correct_values(area_fees):
        assert area_fees.prices_as_dict() == {
            "taxes_surcharges": 0.1,
            "other_fee": 0.1,
            "monthly_fee": 0.002,
            "other_monthly_fee": 0.0002,
        }

    @staticmethod
    def test_total_monthly_fee_price_returns_correct_values(area_fees):
        assert area_fees.total_monthly_fee_price == 0.4

    @staticmethod
    def test_total_monthly_fees_returns_correct_values(area_fees):
        assert area_fees.total_monthly_fees == 0.0022

    @staticmethod
    def test_total_per_kWh_fee_price_returns_correct_values(area_fees):
        assert area_fees.total_per_kWh_fee_price == 0.2

    @staticmethod
    def test_add_fees_to_energy_rate_returns_correct_values(area_fees):
        assert area_fees.add_fees_to_energy_rate(0.33) == 0.341

    @staticmethod
    def test_add_price_to_fees_adapts_prices_correctly(area_fees):
        area_fees.add_price_to_fees(0.33)
        expected_prices = {"taxes_surcharges": 0.1033, "other_fee": 0.10033}
        for name, fee in area_fees.per_kWh_fees.items():
            assert fee.price == expected_prices[name]

    @staticmethod
    def test_decreased_grid_fee_returns_correct_values(area_fees):
        assert isclose(area_fees.decreased_grid_fee, 0.18, abs_tol=1e-2)


class TestAreaEnergyRates:

    @staticmethod
    def test_intracommunity_rate_returns_correct_value(area_energy_rates):
        assert area_energy_rates.intracommunity_rate == 11.18

    @staticmethod
    def test_utility_rate_incl_fees_returns_correct_value(area_energy_rates):
        assert area_energy_rates.utility_rate_incl_fees == 30.2

    @staticmethod
    def test_accumulate_fees_in_community_correctly_accumulates_fees(area_energy_rates):
        # Given
        assert area_energy_rates.area_fees.per_kWh_fees == {}
        assert area_energy_rates.area_fees.monthly_fees == {}
        area_fees = AreaFees(
            grid_import_fee_const=0.2,
            grid_export_fee_const=0.1,
            grid_fees_reduction=0.1,
            per_kWh_fees={
                "taxes_surcharges": FeeContainer(value=0.01, price=0.1),
                "other_fee": FeeContainer(value=0.001, price=0.1),
            },
            monthly_fees={
                "monthly_fee": FeeContainer(value=0.002, price=0.2),
                "other_monthly_fee": FeeContainer(value=0.0002, price=0.2),
            },
        )
        # When calling the method 2 times
        area_energy_rates.accumulate_fees_in_community(area_fees)
        area_energy_rates.accumulate_fees_in_community(area_fees)

        # Then
        assert area_energy_rates.area_fees.per_kWh_fees == {
            "other_fee": FeeContainer(value=0.0, price=0.2),
            "taxes_surcharges": FeeContainer(value=0.0, price=0.2),
        }
        assert area_energy_rates.area_fees.monthly_fees == {
            "monthly_fee": FeeContainer(value=0.0, price=0.4),
            "other_monthly_fee": FeeContainer(value=0.0, price=0.4),
        }


class TestHomeAfterMeterData:

    @staticmethod
    @pytest.mark.parametrize("disable_home_self_consumption", [True, False])
    def test_post_init_sets_default_values_correctly(disable_home_self_consumption):
        gsy_e.constants.SCM_DISABLE_HOME_SELF_CONSUMPTION = disable_home_self_consumption
        home_after_meter_data = HomeAfterMeterData(
            home_uuid="uuid",
            home_name="home name",
            energy_surplus_kWh=0.3,
            energy_need_kWh=1,
            consumption_kWh=0.1,
            production_kWh=2,
        )
        if disable_home_self_consumption:
            assert home_after_meter_data.self_consumed_energy_kWh == 0.0
            assert home_after_meter_data.energy_surplus_kWh == 2
            assert home_after_meter_data.energy_need_kWh == 0.1
        else:
            assert home_after_meter_data.self_consumed_energy_kWh == 0.1
            assert home_after_meter_data.energy_surplus_kWh == 1.9
            assert home_after_meter_data.energy_need_kWh == 0.0

    @staticmethod
    def test_set_total_community_production_correctly_sets_value(home_after_meter_data):
        home_after_meter_data.set_total_community_production(2)
        assert home_after_meter_data.community_total_production_kWh == 2

    @staticmethod
    @pytest.mark.parametrize("unassigned_energy_production_kWh", [0.01, 2])
    def test_set_production_for_community_correctly_stets_values(
        home_after_meter_data, unassigned_energy_production_kWh
    ):
        home_after_meter_data.energy_surplus_kWh = 0.1
        return_value = home_after_meter_data.set_production_for_community(
            unassigned_energy_production_kWh
        )
        if unassigned_energy_production_kWh == 2:
            assert home_after_meter_data._self_production_for_community_kWh == 0.1
            assert return_value == 1.9
        else:
            assert home_after_meter_data._self_production_for_community_kWh == 0.01
            assert return_value == 0.0

    @staticmethod
    def test_self_production_for_community_kWh_returns_correct_value(home_after_meter_data):
        home_after_meter_data._self_production_for_community_kWh = 2
        assert home_after_meter_data.self_production_for_community_kWh == 2

    @staticmethod
    def test_self_production_for_grid_kWh_returns_correct_value(home_after_meter_data):
        home_after_meter_data.energy_surplus_kWh = 2
        assert home_after_meter_data.self_production_for_grid_kWh == 2

    @staticmethod
    def test_allocated_community_energy_kWh_returns_correct_value(home_after_meter_data):
        home_after_meter_data.community_total_production_kWh = 2
        home_after_meter_data.area_properties.AREA_PROPERTIES["coefficient_percentage"] = 0.1
        assert home_after_meter_data.allocated_community_energy_kWh == 0.2

    @staticmethod
    @pytest.mark.parametrize("energy_need_kWh", [0.1, 2])
    def test_energy_bought_from_community_kWh_returns_correct_value(
        home_after_meter_data, energy_need_kWh
    ):
        home_after_meter_data.community_total_production_kWh = 2
        home_after_meter_data.area_properties.AREA_PROPERTIES["coefficient_percentage"] = 0.1
        home_after_meter_data.energy_need_kWh = energy_need_kWh
        if energy_need_kWh == 0.1:
            assert home_after_meter_data.energy_bought_from_community_kWh == 0.1
        else:
            assert home_after_meter_data.energy_bought_from_community_kWh == 0.2

    @staticmethod
    def test_energy_sold_to_grid_kWh_returns_correct_value(home_after_meter_data):
        home_after_meter_data.energy_surplus_kWh = 2
        home_after_meter_data._self_production_for_community_kWh = 0.1
        assert home_after_meter_data.self_production_for_grid_kWh == 1.9

    @staticmethod
    def test_energy_sold_to_grid_kWh_thows_error_log_of_wrong_calculation(
        caplog, home_after_meter_data
    ):
        home_after_meter_data.production_kWh = 2
        home_after_meter_data.energy_surplus_kWh = 3
        home_after_meter_data._self_production_for_community_kWh = 3

        with caplog.at_level(logging.ERROR):
            _ = home_after_meter_data.energy_sold_to_grid_kWh
        assert "Incorrect SCM calculation of sold to grid" in caplog.text

    @staticmethod
    def test_create_buy_trade_correctly_adds_a_trade(home_after_meter_data):
        # Given
        home_after_meter_data.energy_need_kWh = 5
        # When
        time_slot = datetime(2025, 3, 12, 14)
        home_after_meter_data.create_buy_trade(
            current_time_slot=time_slot,
            seller_name="seller",
            traded_energy_kWh=2,
            trade_price_cents=60,
        )
        # Then
        assert len(home_after_meter_data.trades) == 1
        assert home_after_meter_data.trades[0].traded_energy == 2
        assert home_after_meter_data.trades[0].trade_price == 60
        assert home_after_meter_data.trades[0].time_slot == time_slot
        assert home_after_meter_data.trades[0].traded_energy == 2

    @staticmethod
    def test_create_sell_trade_correctly_adds_a_trade(home_after_meter_data):
        # Given
        home_after_meter_data.energy_surplus_kWh = 5
        # When
        time_slot = datetime(2025, 3, 12, 14)
        home_after_meter_data.create_sell_trade(
            current_time_slot=time_slot,
            buyer_name="buyer",
            traded_energy_kWh=2,
            trade_price_cents=60,
        )
        # Then
        assert len(home_after_meter_data.trades) == 1
        assert home_after_meter_data.trades[0].traded_energy == 2
        assert home_after_meter_data.trades[0].trade_price == 60
        assert home_after_meter_data.trades[0].time_slot == time_slot
        assert home_after_meter_data.trades[0].traded_energy == 2


class TestHomeAfterMeterDataWithoutSurplusTrade:

    @staticmethod
    def test_set_production_for_community_correctly_stets_values(home_after_meter_data):
        return_value = HomeAfterMeterDataWithoutSurplusTrade(
            home_uuid="uuid", home_name="home name"
        ).set_production_for_community(2)
        assert home_after_meter_data._self_production_for_community_kWh == 0.0
        assert return_value == 0.0


class TestAreaEnergyBills:

    @staticmethod
    def test_set_bought_from_community_sets_values_correctly(area_energy_bills):
        area_energy_bills.energy_rates.area_fees.add_price_to_fees = Mock()
        area_energy_bills.set_bought_from_community(2)
        assert area_energy_bills.bought_from_community == 2
        assert area_energy_bills.spent_to_community == 22.36
        assert area_energy_bills.gsy_energy_bill == 22.36
        assert isclose(area_energy_bills.import_grid_fees, 0.36)
        area_energy_bills.energy_rates.area_fees.add_price_to_fees.assert_called_once_with(2)

    @staticmethod
    def test_set_sold_to_community_sets_values_correctly(area_energy_bills):
        area_energy_bills.set_sold_to_community(2, 0.3)
        assert area_energy_bills.sold_to_community == 2
        assert area_energy_bills.earned_from_community == 0.6
        assert area_energy_bills.gsy_energy_bill == -0.6

    @staticmethod
    def test_set_bought_from_grid_sets_values_correctly(area_energy_bills):
        area_energy_bills.energy_rates.area_fees.add_price_to_fees = Mock()
        area_energy_bills.set_bought_from_grid(2)
        assert area_energy_bills.bought_from_grid == 2
        assert area_energy_bills.spent_to_grid == 60.4
        assert area_energy_bills.gsy_energy_bill == 60.4
        assert isclose(area_energy_bills.import_grid_fees, 0.4)
        area_energy_bills.energy_rates.area_fees.add_price_to_fees.assert_called_once_with(2)

    @staticmethod
    def test_set_sold_to_grid_sets_values_correctly(area_energy_bills):
        area_energy_bills.set_sold_to_grid(2, 0.3)
        assert area_energy_bills.sold_to_grid == 2
        assert area_energy_bills.earned_from_grid == 0.6
        assert area_energy_bills.gsy_energy_bill == -0.6

    @staticmethod
    def test_set_export_grid_fees_sets_values_correctly(area_energy_bills):
        area_energy_bills.set_export_grid_fees(2)
        assert area_energy_bills.export_grid_fees == 0.02

    @staticmethod
    def test_set_min_max_community_savings_values_correctly(area_energy_bills):
        area_energy_bills.set_min_max_community_savings(0.1, 0.9)
        assert area_energy_bills._min_community_savings_percent == 0.1
        assert area_energy_bills._max_community_savings_percent == 0.9

    @staticmethod
    def test_savings_from_buy_from_community_returns_correct_values(area_energy_bills):
        area_energy_bills.bought_from_community = 2
        assert area_energy_bills.savings_from_buy_from_community == 38.04

    @staticmethod
    def test_savings_from_sell_to_community_returns_correct_values(area_energy_bills):
        area_energy_bills.sold_to_community = 2
        assert area_energy_bills.savings_from_sell_to_community == 8.36

    @staticmethod
    def test_savings_returns_correct_values(area_energy_bills):
        area_energy_bills.bought_from_community = 2
        area_energy_bills.sold_to_community = 2
        assert area_energy_bills.savings == 46.4

    @staticmethod
    def test_savings_percent_returns_correct_values(area_energy_bills):
        area_energy_bills.bought_from_community = 2
        area_energy_bills.sold_to_community = 2
        area_energy_bills.base_energy_bill_excl_revenue = 80
        assert isclose(area_energy_bills.savings_percent, 58)

    @staticmethod
    def test_energy_benchmark_correct_values(area_energy_bills):
        area_energy_bills.bought_from_community = 2
        area_energy_bills.sold_to_community = 2
        area_energy_bills.base_energy_bill_excl_revenue = 80
        area_energy_bills._min_community_savings_percent = 0.1
        area_energy_bills._max_community_savings_percent = 0.8
        area_energy_bills.base_energy_bill_excl_revenue = 80
        assert isclose(area_energy_bills.energy_benchmark, 82.714, abs_tol=1e-3)

    @staticmethod
    def test_gsy_energy_bill_excl_revenue_returns_correct_values(area_energy_bills):
        area_energy_bills.gsy_energy_bill = 2
        area_energy_bills.earned_from_grid = 2
        area_energy_bills.earned_from_community = 1
        assert area_energy_bills.gsy_energy_bill_excl_revenue == 5

    @staticmethod
    def test_gsy_energy_bill_excl_revenue_without_fees_returns_correct_values(area_energy_bills):
        area_energy_bills.gsy_energy_bill = 2
        area_energy_bills.earned_from_grid = 2
        area_energy_bills.earned_from_community = 1
        area_energy_bills.import_grid_fees = 0.1
        assert area_energy_bills.gsy_energy_bill_excl_revenue == 5

    @staticmethod
    def test_gsy_energy_bill_revenue_returns_correct_values(area_energy_bills):
        area_energy_bills.earned_from_grid = 2
        area_energy_bills.earned_from_community = 2
        assert area_energy_bills.gsy_energy_bill_revenue == 4

    @staticmethod
    def test_gsy_energy_bill_excl_fees_returns_correct_values(area_energy_bills):
        area_energy_bills.gsy_energy_bill = 2
        area_energy_bills.earned_from_grid = 2
        area_energy_bills.earned_from_community = 1
        area_energy_bills.import_grid_fees = 0.1
        assert area_energy_bills.gsy_energy_bill_excl_fees == 1.9

    @staticmethod
    def test_gsy_total_benefit_returns_correct_values(area_energy_bills):
        area_energy_bills.bought_from_community = 2
        area_energy_bills.sold_to_community = 2
        area_energy_bills.energy_rates.area_fees.monthly_fees = {
            "some_fee": FeeContainer(price=0.1)
        }
        assert area_energy_bills.gsy_total_benefit == 46.3

    @staticmethod
    def test_home_balance_returns_correct_values(area_energy_bills):
        area_energy_bills.spent_to_grid = 2
        area_energy_bills.spent_to_community = 2
        area_energy_bills.earned_from_grid = 1
        area_energy_bills.earned_from_community = 1
        assert area_energy_bills.home_balance == 2

    @staticmethod
    def test_calculate_base_energy_bill_sets_values_correctly(
        area_energy_bills, home_after_meter_data, area_energy_rates
    ):
        home_after_meter_data.energy_surplus_kWh = 1
        home_after_meter_data.energy_need_kWh = 2
        area_energy_bills.calculate_base_energy_bill(
            home_data=home_after_meter_data, area_rates=area_energy_rates
        )
        assert area_energy_bills.base_energy_bill_revenue == 7
        assert area_energy_bills.base_energy_bill_excl_revenue == 60.4
        assert area_energy_bills.base_energy_bill == 53.4


class TestAreaEnergyBillsWithoutSurplusTrade:

    @staticmethod
    def test_savings_from_buy_from_community_returns_correct_values(
        area_energy_bills_without_surplus_trade,
    ):
        area_energy_bills_without_surplus_trade.bought_from_community = 2
        assert area_energy_bills_without_surplus_trade.savings_from_buy_from_community == 60.4

    @staticmethod
    def test_savings_from_sell_to_community_returns_correct_values(
        area_energy_bills_without_surplus_trade,
    ):
        area_energy_bills_without_surplus_trade.earned_from_grid = 2
        area_energy_bills_without_surplus_trade.earned_from_community = 1
        assert area_energy_bills_without_surplus_trade.savings_from_sell_to_community == 3

    @staticmethod
    def test_calculate_base_energy_bill_sets_values_correctly(
        area_energy_bills_without_surplus_trade, home_after_meter_data, area_energy_rates
    ):
        home_after_meter_data.consumption_kWh = 1
        home_after_meter_data.energy_need_kWh = 2
        area_energy_bills_without_surplus_trade.calculate_base_energy_bill(
            home_data=home_after_meter_data, area_rates=area_energy_rates
        )
        assert area_energy_bills_without_surplus_trade.base_energy_bill_revenue == 0
        assert area_energy_bills_without_surplus_trade.base_energy_bill_excl_revenue == 30.2
        assert area_energy_bills_without_surplus_trade.base_energy_bill == 30.2
