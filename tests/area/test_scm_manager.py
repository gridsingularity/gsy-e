# pylint: disable=protected-access
import uuid
from math import isclose
from unittest.mock import MagicMock, patch
from copy import deepcopy

import pytest
from gsy_framework.data_classes import Trade
from pendulum import datetime

from gsy_e.models.area.coefficient_area import CoefficientArea
from gsy_e.models.area.scm_dataclasses import (
    SCMAreaProperties,
    AreaEnergyBills,
    HomeAfterMeterData,
    HomeAfterMeterDataWithoutSurplusTrade,
    AreaEnergyBillsWithoutSurplusTrade,
)
from gsy_e.models.area.scm_manager import SCMManager, SCMManagerWithoutSurplusTrade
from gsy_e.models.strategy.scm.load import SCMLoadHoursStrategy
from gsy_e.models.strategy.scm.pv import SCMPVUserProfile

TIME_SLOT = datetime(2025, 3, 13, 8)
HOUSE1_UUID = str(uuid.uuid4())
HOUSE2_UUID = str(uuid.uuid4())
HOUSE3_UUID = str(uuid.uuid4())
HOUSE1_NAME = "home1"
HOUSE2_NAME = "home2"
HOUSE3_NAME = "home3"


@pytest.fixture(name="scm_manager")
def fixture_scm_manager():
    strategy = MagicMock(spec=SCMPVUserProfile)
    strategy.get_energy_to_sell_kWh = MagicMock(return_value=0.5)
    strategy.get_energy_to_buy_kWh = MagicMock(return_value=0.0)
    pv = CoefficientArea(name="pv", strategy=strategy)

    strategy = MagicMock(spec=SCMLoadHoursStrategy)
    strategy.get_energy_to_sell_kWh = MagicMock(return_value=0.0)
    strategy.get_energy_to_buy_kWh = MagicMock(return_value=0.7)
    load = CoefficientArea(name="load", strategy=strategy)

    strategy = MagicMock(spec=SCMLoadHoursStrategy)
    strategy.get_energy_to_sell_kWh = MagicMock(return_value=0.0)
    strategy.get_energy_to_buy_kWh = MagicMock(return_value=0.1)
    load2 = CoefficientArea(name="load 2", strategy=strategy)
    house1 = CoefficientArea(name=HOUSE1_NAME, children=[load, pv], uuid=HOUSE1_UUID)
    house2 = CoefficientArea(name=HOUSE2_NAME, children=[load2], uuid=HOUSE2_UUID)
    coefficient_area = CoefficientArea(name="Community", children=[house1, house2])
    with patch("gsy_e.models.area.scm_manager.SCMCommunityValidator.validate", return_value=True):
        return SCMManager(area=coefficient_area, time_slot=TIME_SLOT)


@pytest.fixture(name="scm_manager_without_surplus_trade")
def fixture_scm_manager_without_surplus_trade():
    strategy = MagicMock(spec=SCMPVUserProfile)
    strategy.get_energy_to_sell_kWh = MagicMock(return_value=0.5)
    strategy.get_energy_to_buy_kWh = MagicMock(return_value=0.0)
    pv = CoefficientArea(name="pv", strategy=strategy)

    strategy = MagicMock(spec=SCMLoadHoursStrategy)
    strategy.get_energy_to_sell_kWh = MagicMock(return_value=0.0)
    strategy.get_energy_to_buy_kWh = MagicMock(return_value=0.7)
    load = CoefficientArea(name="load", strategy=strategy)

    strategy = MagicMock(spec=SCMLoadHoursStrategy)
    strategy.get_energy_to_sell_kWh = MagicMock(return_value=0.0)
    strategy.get_energy_to_buy_kWh = MagicMock(return_value=0.1)
    load2 = CoefficientArea(name="load 2", strategy=strategy)
    house1 = CoefficientArea(name=HOUSE1_NAME, children=[load, pv], uuid=HOUSE1_UUID)
    house2 = CoefficientArea(name=HOUSE2_NAME, children=[load2], uuid=HOUSE2_UUID)
    coefficient_area = CoefficientArea(name="Community", children=[house1, house2])
    with patch("gsy_e.models.area.scm_manager.SCMCommunityValidator.validate", return_value=True):
        return SCMManagerWithoutSurplusTrade(area=coefficient_area, time_slot=TIME_SLOT)


@pytest.fixture(name="area_properties_house1")
def fixture_area_properties_house1():
    return SCMAreaProperties(
        GRID_FEES={"grid_import_fee_const": 0.1, "grid_export_fee_const": 0.1},
        PER_KWH_FEES={"fee_1": 0.01, "fee_2": 0.2},
        MONTHLY_FEES={"monthly_fee": 0.3},
        AREA_PROPERTIES={
            "feed_in_tariff": 7,
            "market_maker_rate": 30,
            "coefficient_percentage": 0.6,
        },
    )


@pytest.fixture(name="area_properties_house2")
def fixture_area_properties_house2():
    return SCMAreaProperties(
        GRID_FEES={"grid_import_fee_const": 0.1, "grid_export_fee_const": 0.1},
        PER_KWH_FEES={"fee_1": 0.01, "fee_2": 0.2},
        MONTHLY_FEES={"monthly_fee": 0.3},
        AREA_PROPERTIES={
            "feed_in_tariff": 7,
            "market_maker_rate": 30,
            "coefficient_percentage": 0.4,
        },
    )


class TestSCMManager:

    @staticmethod
    def test_add_home_data_correctly_adds_home_data(scm_manager, area_properties_house1):
        assert len(scm_manager._home_data) == 0
        scm_manager.add_home_data(
            home_uuid=HOUSE1_UUID,
            home_name=HOUSE1_NAME,
            area_properties=area_properties_house1,
            production_kWh=2,
            consumption_kWh=5,
        )
        assert isinstance(scm_manager._home_data[HOUSE1_UUID], HomeAfterMeterData)
        assert scm_manager._home_data[HOUSE1_UUID].home_uuid == HOUSE1_UUID
        assert scm_manager._home_data[HOUSE1_UUID].home_name == HOUSE1_NAME
        assert scm_manager._home_data[HOUSE1_UUID].consumption_kWh == 5
        assert scm_manager._home_data[HOUSE1_UUID].production_kWh == 2
        assert scm_manager._home_data[HOUSE1_UUID].area_properties == area_properties_house1

    @staticmethod
    def test_calculate_community_after_meter_data_correctly_sets_values(
        scm_manager, area_properties_house1, area_properties_house2
    ):
        scm_manager.add_home_data(
            home_uuid=HOUSE1_UUID,
            home_name=HOUSE1_NAME,
            area_properties=area_properties_house1,
            production_kWh=7,
            consumption_kWh=5,
        )
        scm_manager.add_home_data(
            home_uuid=HOUSE2_UUID,
            home_name=HOUSE2_NAME,
            area_properties=area_properties_house2,
            production_kWh=0,
            consumption_kWh=7,
        )

        scm_manager.calculate_community_after_meter_data()
        assert scm_manager.community_data.community_uuid == scm_manager._community_uuid
        assert scm_manager.community_data.production_kWh == 7
        assert scm_manager.community_data.consumption_kWh == 12
        assert scm_manager.community_data.self_consumed_energy_kWh == 5.8
        assert scm_manager.community_data.energy_surplus_kWh == 2
        assert scm_manager.community_data.energy_need_kWh == 7
        assert scm_manager.community_data.energy_bought_from_community_kWh == 0.8
        assert scm_manager.community_data.energy_sold_to_grid_kWh == 1.2

        for home_data in scm_manager._home_data.values():
            assert home_data.community_total_production_kWh == 2
            assert home_data._self_production_for_community_kWh == (
                0.8 if home_data.home_uuid == HOUSE1_UUID else 0
            )

    @staticmethod
    def test_calculate_community_after_meter_data_correctly_distributes_surplus_amongst_members(
        scm_manager, area_properties_house1, area_properties_house2
    ):

        area_properties_house1.AREA_PROPERTIES["coefficient_percentage"] = 0.4
        scm_manager.add_home_data(
            home_uuid=HOUSE1_UUID,
            home_name=HOUSE1_NAME,
            area_properties=area_properties_house1,
            production_kWh=1.4,
            consumption_kWh=1,
        )
        area_properties_house2.AREA_PROPERTIES["coefficient_percentage"] = 0.2
        scm_manager.add_home_data(
            home_uuid=HOUSE2_UUID,
            home_name=HOUSE2_NAME,
            area_properties=area_properties_house2,
            production_kWh=0,
            consumption_kWh=0.5,
        )

        area_properties_house3 = deepcopy(area_properties_house2)
        area_properties_house3.AREA_PROPERTIES["coefficient_percentage"] = 0.4
        scm_manager.add_home_data(
            home_uuid=HOUSE3_UUID,
            home_name=HOUSE3_NAME,
            area_properties=area_properties_house3,
            production_kWh=1.4,
            consumption_kWh=1,
        )
        # When
        scm_manager.calculate_community_after_meter_data()
        assert scm_manager.community_data.community_uuid == scm_manager._community_uuid
        assert scm_manager.community_data.production_kWh == 2.8
        assert scm_manager.community_data.consumption_kWh == 2.5
        assert scm_manager.community_data.self_consumed_energy_kWh == 2.16
        assert isclose(scm_manager.community_data.energy_surplus_kWh, 0.8, abs_tol=1e-3)
        assert scm_manager.community_data.energy_need_kWh == 0.5
        assert isclose(
            scm_manager.community_data.energy_bought_from_community_kWh, 0.16, abs_tol=1e-3
        )
        assert isclose(scm_manager.community_data.energy_sold_to_grid_kWh, 0.64, abs_tol=1e-3)

        for home_data in scm_manager._home_data.values():
            if home_data.home_uuid == HOUSE1_UUID:
                assert isclose(home_data.energy_sold_to_grid_kWh, 0.24, abs_tol=1e-3)
            if home_data.home_uuid == HOUSE2_UUID:
                assert isclose(home_data.energy_sold_to_grid_kWh, 0.0, abs_tol=1e-3)
            if home_data.home_uuid == HOUSE3_UUID:
                assert isclose(home_data.energy_sold_to_grid_kWh, 0.4, abs_tol=1e-3)

    @staticmethod
    @pytest.mark.parametrize("house2_consumption", [7, 0.8])
    def test_calculate_home_energy_bills_correctly_sets_values(
        scm_manager, area_properties_house1, area_properties_house2, house2_consumption
    ):
        # Given
        scm_manager.add_home_data(
            home_uuid=HOUSE1_UUID,
            home_name=HOUSE1_NAME,
            area_properties=area_properties_house1,
            production_kWh=7,
            consumption_kWh=5,
        )
        scm_manager.add_home_data(
            home_uuid=HOUSE2_UUID,
            home_name=HOUSE2_NAME,
            area_properties=area_properties_house2,
            production_kWh=0,
            consumption_kWh=house2_consumption,
        )
        scm_manager.calculate_community_after_meter_data()

        # When
        scm_manager.calculate_home_energy_bills(HOUSE1_UUID)
        # Then
        assert isinstance(scm_manager._bills[HOUSE1_UUID], AreaEnergyBills)
        assert isclose(scm_manager._bills[HOUSE1_UUID].base_energy_bill, -13.999, abs_tol=1e-3)
        assert isclose(
            scm_manager._bills[HOUSE1_UUID].base_energy_bill_excl_revenue, 0.0001, abs_tol=1e-3
        )
        assert isclose(scm_manager._bills[HOUSE1_UUID].base_energy_bill_revenue, 14, abs_tol=1e-3)
        assert isclose(scm_manager._bills[HOUSE1_UUID].gsy_energy_bill, -32.457, abs_tol=1e-3)
        assert isclose(scm_manager._bills[HOUSE1_UUID].bought_from_community, 0.0)
        assert isclose(scm_manager._bills[HOUSE1_UUID].spent_to_community, 0.0)
        assert isclose(scm_manager._bills[HOUSE1_UUID].sold_to_community, 0.8)
        assert isclose(scm_manager._bills[HOUSE1_UUID].earned_from_community, 24.0576)
        assert isclose(scm_manager._bills[HOUSE1_UUID].bought_from_grid, 0.0)

        # When
        scm_manager.calculate_home_energy_bills(HOUSE2_UUID)
        # Then
        if house2_consumption == 0.8:
            assert isinstance(scm_manager._bills[HOUSE2_UUID], AreaEnergyBills)
            assert isclose(scm_manager._bills[HOUSE2_UUID].base_energy_bill, 24.248, abs_tol=1e-3)
            assert isclose(
                scm_manager._bills[HOUSE2_UUID].base_energy_bill_excl_revenue, 24.248, abs_tol=1e-3
            )
            assert isclose(scm_manager._bills[HOUSE2_UUID].gsy_energy_bill, 24.057, abs_tol=1e-3)
            assert isclose(scm_manager._bills[HOUSE2_UUID].bought_from_grid, 0.0)
        else:
            assert isinstance(scm_manager._bills[HOUSE2_UUID], AreaEnergyBills)
            assert isclose(scm_manager._bills[HOUSE2_UUID].base_energy_bill, 212.17, abs_tol=1e-3)
            assert isclose(
                scm_manager._bills[HOUSE2_UUID].base_energy_bill_excl_revenue, 212.17, abs_tol=1e-3
            )
            assert isclose(scm_manager._bills[HOUSE2_UUID].gsy_energy_bill, 211.979, abs_tol=1e-3)
            assert isclose(scm_manager._bills[HOUSE2_UUID].bought_from_grid, 6.2)

        assert isclose(scm_manager._bills[HOUSE2_UUID].base_energy_bill_revenue, 0, abs_tol=1e-3)
        assert isclose(scm_manager._bills[HOUSE2_UUID].bought_from_community, 0.8)
        assert isclose(scm_manager._bills[HOUSE2_UUID].spent_to_community, 24.0576)
        assert isclose(scm_manager._bills[HOUSE2_UUID].sold_to_community, 0.0)
        assert isclose(scm_manager._bills[HOUSE2_UUID].earned_from_community, 0.0)

    @staticmethod
    def test_accumulate_community_trades_correctly_gathers_trades_from_all_homes(
        scm_manager, area_properties_house1, area_properties_house2
    ):
        # Given
        scm_manager.add_home_data(
            home_uuid=HOUSE1_UUID,
            home_name=HOUSE1_NAME,
            area_properties=area_properties_house1,
            production_kWh=7,
            consumption_kWh=5,
        )
        scm_manager.add_home_data(
            home_uuid=HOUSE2_UUID,
            home_name=HOUSE2_NAME,
            area_properties=area_properties_house2,
            production_kWh=0,
            consumption_kWh=7,
        )

        scm_manager.calculate_community_after_meter_data()
        scm_manager.calculate_home_energy_bills(HOUSE1_UUID)
        scm_manager.calculate_home_energy_bills(HOUSE2_UUID)

        # When
        scm_manager.accumulate_community_trades()

        # Then
        assert len(scm_manager.community_data.trades) == 4
        saved_trades_simplyfied = [
            {"seller": trade.seller.name, "buyer": trade.buyer.name, "energy": trade.traded_energy}
            for trade in scm_manager.community_data.trades
        ]

        assert {"seller": "home1", "buyer": "Community", "energy": 0.8} in saved_trades_simplyfied
        assert {"seller": "home1", "buyer": "Grid", "energy": 1.2} in saved_trades_simplyfied
        assert {"seller": "Community", "buyer": "home2", "energy": 0.8} in saved_trades_simplyfied
        assert {"seller": "Grid", "buyer": "home2", "energy": 6.2} in saved_trades_simplyfied

    @staticmethod
    @pytest.mark.parametrize("serializable", [True, False])
    def test_get_area_results_returns_correct_results(
        scm_manager, area_properties_house1, area_properties_house2, serializable
    ):
        # Given
        scm_manager.add_home_data(
            home_uuid=HOUSE1_UUID,
            home_name=HOUSE1_NAME,
            area_properties=area_properties_house1,
            production_kWh=7,
            consumption_kWh=5,
        )
        scm_manager.add_home_data(
            home_uuid=HOUSE2_UUID,
            home_name=HOUSE2_NAME,
            area_properties=area_properties_house2,
            production_kWh=0,
            consumption_kWh=7,
        )

        scm_manager.calculate_community_after_meter_data()
        scm_manager.calculate_home_energy_bills(HOUSE1_UUID)
        scm_manager.calculate_home_energy_bills(HOUSE2_UUID)
        scm_manager.accumulate_community_trades()

        # When
        return_value = scm_manager.get_area_results(HOUSE1_UUID, serializable=serializable)

        # Then
        assert all(key in return_value for key in ["bills", "after_meter_data", "trades"])
        # TODO: why do we export the trades twice?
        if serializable:
            assert all(
                isinstance(trade, dict) for trade in return_value["after_meter_data"]["trades"]
            )
            assert all(isinstance(trade, dict) for trade in return_value["trades"])
        else:
            assert all(
                isinstance(trade, Trade) for trade in return_value["after_meter_data"]["trades"]
            )
            assert all(isinstance(trade, dict) for trade in return_value["trades"])

        assert return_value["bills"] == {
            "base_energy_bill": -13.999899193548387,
            "base_energy_bill_excl_revenue": 0.00010080645161290323,
            "base_energy_bill_revenue": 14,
            "gsy_energy_bill": -32.45749919354839,
            "bought_from_community": 0.0,
            "spent_to_community": 0.0,
            "sold_to_community": 0.8,
            "earned_from_community": 24.0576,
            "bought_from_grid": 0.0,
            "spent_to_grid": 0.0,
            "sold_to_grid": 1.2,
            "earned_from_grid": 8.4,
            "import_grid_fees": 0.0,
            "export_grid_fees": 0.12,
            "_min_community_savings_percent": 0.08973931731016684,
            "_max_community_savings_percent": 18309939.2,
            "fees": {"monthly_fee": 0.00010080645161290323, "fee_1": 0.0, "fee_2": 0.0},
            "savings": 18.4576,
            "savings_percent": 18309939.2,
            "energy_benchmark": 1.0,
            "home_balance_kWh": -2.0,
            "home_balance": -32.4576,
            "gsy_energy_bill_excl_revenue": 0.00010080645161281154,
            "gsy_energy_bill_excl_revenue_without_fees": 0.00010080645161281154,
            "gsy_energy_bill_excl_fees": -32.45749919354839,
            "gsy_energy_bill_revenue": 32.4576,
            "gsy_total_benefit": 18.4576,
        }

        return_value["after_meter_data"].pop("trades")
        assert return_value["after_meter_data"] == {
            "home_uuid": HOUSE1_UUID,
            "home_name": HOUSE1_NAME,
            "consumption_kWh": 5,
            "production_kWh": 7,
            "self_consumed_energy_kWh": 5,
            "energy_surplus_kWh": 2,
            "energy_need_kWh": 0,
            "community_total_production_kWh": 2.0,
            "_self_production_for_community_kWh": 0.8,
            "area_properties": {
                "GRID_FEES": {"grid_import_fee_const": 0.1, "grid_export_fee_const": 0.1},
                "PER_KWH_FEES": {"fee_1": 0.01, "fee_2": 0.2},
                "MONTHLY_FEES": {"monthly_fee": 0.3},
                "AREA_PROPERTIES": {
                    "feed_in_tariff": 7,
                    "market_maker_rate": 30,
                    "coefficient_percentage": 0.6,
                },
            },
            "allocated_community_energy_kWh": 1.2,
            "energy_bought_from_community_kWh": 0,
            "energy_sold_to_grid_kWh": 1.2,
        }

    @staticmethod
    def test_get_after_meter_data_returns_correct_values(scm_manager, area_properties_house1):
        # Given
        scm_manager.add_home_data(
            home_uuid=HOUSE1_UUID,
            home_name=HOUSE1_NAME,
            area_properties=area_properties_house1,
            production_kWh=7,
            consumption_kWh=5,
        )

        scm_manager.calculate_community_after_meter_data()
        scm_manager.calculate_home_energy_bills(HOUSE1_UUID)

        # When
        return_value = scm_manager.get_after_meter_data(HOUSE1_UUID)

        # Then
        assert isinstance(return_value, HomeAfterMeterData)
        print(return_value)
        assert return_value.home_uuid == HOUSE1_UUID
        assert return_value.home_name == HOUSE1_NAME
        assert return_value.consumption_kWh == 5
        assert return_value.production_kWh == 7
        assert return_value.self_consumed_energy_kWh == 5
        assert return_value.energy_surplus_kWh == 2
        assert return_value.energy_need_kWh == 0
        assert return_value.community_total_production_kWh == 2
        assert return_value._self_production_for_community_kWh == 0
        assert all(isinstance(trade, Trade) for trade in return_value.trades)

    @staticmethod
    def test_get_home_energy_need_returns_correct_values(scm_manager, area_properties_house1):
        # Given
        scm_manager.add_home_data(
            home_uuid=HOUSE1_UUID,
            home_name=HOUSE1_NAME,
            area_properties=area_properties_house1,
            production_kWh=7,
            consumption_kWh=5,
        )

        scm_manager.calculate_community_after_meter_data()
        scm_manager.calculate_home_energy_bills(HOUSE1_UUID)
        scm_manager._home_data[HOUSE1_UUID].energy_need_kWh = 2

        # When
        return_value = scm_manager.get_home_energy_need(HOUSE1_UUID)

        # Then
        assert return_value == 2

    @staticmethod
    def test_community_bills_returns_correct_values(
        scm_manager, area_properties_house1, area_properties_house2
    ):

        # Given
        scm_manager.add_home_data(
            home_uuid=HOUSE1_UUID,
            home_name=HOUSE1_NAME,
            area_properties=area_properties_house1,
            production_kWh=7,
            consumption_kWh=5,
        )
        scm_manager.add_home_data(
            home_uuid=HOUSE2_UUID,
            home_name=HOUSE2_NAME,
            area_properties=area_properties_house2,
            production_kWh=0,
            consumption_kWh=7,
        )

        scm_manager.calculate_community_after_meter_data()
        scm_manager.calculate_home_energy_bills(HOUSE1_UUID)
        scm_manager.calculate_home_energy_bills(HOUSE2_UUID)
        scm_manager.accumulate_community_trades()

        # When
        community_bills = scm_manager.community_bills

        # Then
        assert community_bills == {
            "base_energy_bill": 198.17020161290327,
            "base_energy_bill_excl_revenue": 212.17020161290327,
            "base_energy_bill_revenue": 14.0,
            "gsy_energy_bill": 179.52220161290325,
            "bought_from_community": 0.8,
            "spent_to_community": 24.0576,
            "sold_to_community": 0.8,
            "earned_from_community": 24.0576,
            "bought_from_grid": 6.2,
            "spent_to_grid": 187.92200000000003,
            "sold_to_grid": 1.2,
            "earned_from_grid": 8.4,
            "import_grid_fees": 0.6776000000000001,
            "export_grid_fees": 0.12,
            "_min_community_savings_percent": 0.0,
            "_max_community_savings_percent": 0.0,
            "fees": {"monthly_fee": 0.0, "fee_1": 0.07, "fee_2": 1.4000000000000004},
            "savings": 18.648000000000003,
            "savings_percent": 0.0,
            "energy_benchmark": None,
            "home_balance_kWh": 5.0,
            "home_balance": 179.52200000000002,
            "gsy_energy_bill_excl_revenue": 211.97980161290326,
            "gsy_energy_bill_excl_revenue_without_fees": 209.83220161290325,
            "gsy_energy_bill_excl_fees": 177.37460161290323,
            "gsy_energy_bill_revenue": 32.4576,
            "gsy_total_benefit": 0.0,
            "savings_from_buy_from_community": 0.19040000000000248,
            "savings_from_sell_to_community": 18.4576,
        }


class TestSCMManagerWithoutSurplusTrade:

    @staticmethod
    def test_add_home_data_correctly_adds_home_data(
        scm_manager_without_surplus_trade, area_properties_house1
    ):
        assert len(scm_manager_without_surplus_trade._home_data) == 0
        scm_manager_without_surplus_trade.add_home_data(
            home_uuid=HOUSE1_UUID,
            home_name=HOUSE1_NAME,
            area_properties=area_properties_house1,
            production_kWh=2,
            consumption_kWh=5,
        )
        assert isinstance(
            scm_manager_without_surplus_trade._home_data[HOUSE1_UUID],
            HomeAfterMeterDataWithoutSurplusTrade,
        )
        assert scm_manager_without_surplus_trade._home_data[HOUSE1_UUID].home_uuid == HOUSE1_UUID
        assert scm_manager_without_surplus_trade._home_data[HOUSE1_UUID].home_name == HOUSE1_NAME
        assert scm_manager_without_surplus_trade._home_data[HOUSE1_UUID].consumption_kWh == 5
        assert scm_manager_without_surplus_trade._home_data[HOUSE1_UUID].production_kWh == 2
        assert (
            scm_manager_without_surplus_trade._home_data[HOUSE1_UUID].area_properties
            == area_properties_house1
        )

    @staticmethod
    @pytest.mark.parametrize("house2_consumption", [7, 0.8])
    def test_calculate_home_energy_bills_correctly_sets_values(
        scm_manager_without_surplus_trade,
        area_properties_house1,
        area_properties_house2,
        house2_consumption,
    ):
        scm_manager = scm_manager_without_surplus_trade
        print(HOUSE1_UUID)
        # Given
        scm_manager.add_home_data(
            home_uuid=HOUSE1_UUID,
            home_name=HOUSE1_NAME,
            area_properties=area_properties_house1,
            production_kWh=7,
            consumption_kWh=5,
        )
        scm_manager.add_home_data(
            home_uuid=HOUSE2_UUID,
            home_name=HOUSE2_NAME,
            area_properties=area_properties_house2,
            production_kWh=0,
            consumption_kWh=house2_consumption,
        )
        scm_manager.calculate_community_after_meter_data()

        # When
        scm_manager.calculate_home_energy_bills(HOUSE1_UUID)
        # Then
        assert isinstance(scm_manager._bills[HOUSE1_UUID], AreaEnergyBillsWithoutSurplusTrade)
        assert isclose(scm_manager._bills[HOUSE1_UUID].base_energy_bill, 151.550, abs_tol=1e-3)
        assert isclose(
            scm_manager._bills[HOUSE1_UUID].base_energy_bill_excl_revenue, 151.55, abs_tol=1e-3
        )
        assert isclose(scm_manager._bills[HOUSE1_UUID].base_energy_bill_revenue, 0)
        assert isclose(scm_manager._bills[HOUSE1_UUID].gsy_energy_bill, -14, abs_tol=1e-3)
        assert isclose(scm_manager._bills[HOUSE1_UUID].bought_from_community, 0.0)
        assert isclose(scm_manager._bills[HOUSE1_UUID].spent_to_community, 0.0)
        assert isclose(scm_manager._bills[HOUSE1_UUID].sold_to_community, 0.0)
        assert isclose(scm_manager._bills[HOUSE1_UUID].earned_from_community, 0)
        assert isclose(scm_manager._bills[HOUSE1_UUID].bought_from_grid, 0.0)

        # When
        scm_manager.calculate_home_energy_bills(HOUSE2_UUID)
        # Then
        if house2_consumption == 0.8:
            assert isinstance(scm_manager._bills[HOUSE2_UUID], AreaEnergyBills)
            assert isclose(scm_manager._bills[HOUSE2_UUID].base_energy_bill, 24.248, abs_tol=1e-3)
            assert isclose(
                scm_manager._bills[HOUSE2_UUID].base_energy_bill_excl_revenue, 24.248, abs_tol=1e-3
            )
            assert isclose(scm_manager._bills[HOUSE2_UUID].gsy_energy_bill, 24.248, abs_tol=1e-3)
            assert isclose(scm_manager._bills[HOUSE2_UUID].bought_from_grid, 0.8)
        else:
            assert isinstance(scm_manager._bills[HOUSE2_UUID], AreaEnergyBills)
            assert isclose(scm_manager._bills[HOUSE2_UUID].base_energy_bill, 212.17, abs_tol=1e-3)
            assert isclose(
                scm_manager._bills[HOUSE2_UUID].base_energy_bill_excl_revenue, 212.17, abs_tol=1e-3
            )
            assert isclose(scm_manager._bills[HOUSE2_UUID].gsy_energy_bill, 212.17, abs_tol=1e-3)
            assert isclose(scm_manager._bills[HOUSE2_UUID].bought_from_grid, 7)

        assert isclose(scm_manager._bills[HOUSE2_UUID].base_energy_bill_revenue, 0, abs_tol=1e-3)
        assert isclose(scm_manager._bills[HOUSE2_UUID].bought_from_community, 0)
        assert isclose(scm_manager._bills[HOUSE2_UUID].spent_to_community, 0)
        assert isclose(scm_manager._bills[HOUSE2_UUID].sold_to_community, 0.0)
        assert isclose(scm_manager._bills[HOUSE2_UUID].earned_from_community, 0.0)
