# pylint: disable=protected-access
import uuid
from math import isclose
from unittest.mock import MagicMock, patch
import pytest
from pendulum import datetime

from gsy_e.models.area.coefficient_area import CoefficientArea
from gsy_e.models.area.scm_dataclasses import SCMAreaProperties, AreaEnergyBills
from gsy_e.models.area.scm_manager import SCMManager
from gsy_e.models.strategy.scm.load import SCMLoadHoursStrategy
from gsy_e.models.strategy.scm.pv import SCMPVUserProfile


TIME_SLOT = datetime(2025, 3, 13, 8)
HOUSE1_UUID = str(uuid.uuid4())
HOUSE2_UUID = str(uuid.uuid4())
HOUSE1_NAME = "home1"
HOUSE2_NAME = "home2"


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
        simplified_trades = [
            {"seller": trade.seller.name, "buyer": trade.buyer.name, "energy": trade.traded_energy}
            for trade in scm_manager.community_data.trades
        ]

        assert {"seller": "home1", "buyer": "Community", "energy": 0.8} in simplified_trades
        assert {"seller": "home1", "buyer": "Grid", "energy": 1.2} in simplified_trades
        assert {"seller": "Community", "buyer": "home2", "energy": 0.8} in simplified_trades
        assert {"seller": "Grid", "buyer": "home2", "energy": 6.2} in simplified_trades
