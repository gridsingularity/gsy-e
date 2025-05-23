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
from math import isclose
from unittest.mock import MagicMock, patch

from gsy_framework.constants_limits import ConstSettings, TIME_ZONE
from gsy_framework.enums import (
    SpotMarketTypeEnum,
    CoefficientAlgorithm,
    SCMPropertyType,
    SCMSelfConsumptionType,
)
from pendulum import duration, today
from pendulum import now
import pytest

from gsy_e.models.area import CoefficientArea, CoefficientAreaException
from gsy_e.models.area.scm_manager import (
    SCMManager,
    HomeAfterMeterData,
    AreaEnergyBills,
    SCMManagerWithoutSurplusTrade,
)
from gsy_e.models.config import SimulationConfig
from gsy_e.models.strategy.scm.load import SCMLoadHoursStrategy
from gsy_e.models.strategy.scm.pv import SCMPVUserProfile


class TestCoefficientArea:
    # pylint: disable=protected-access
    """Test the Area class behavior and state controllers."""

    @staticmethod
    @pytest.fixture(name="config")
    def config_fixture():
        """Instantiate a mocked configuration."""
        config = MagicMock(spec=SimulationConfig)
        config.slot_length = duration(minutes=15)
        config.tick_length = duration(seconds=15)
        config.ticks_per_slot = int(config.slot_length.seconds / config.tick_length.seconds)
        config.start_date = today(tz=TIME_ZONE)
        config.sim_duration = duration(days=1)

        return config

    @staticmethod
    def setup_method():
        ConstSettings.SCMSettings.MARKET_ALGORITHM = 1
        ConstSettings.MASettings.MARKET_TYPE = SpotMarketTypeEnum.COEFFICIENTS.value

    @staticmethod
    def teardown_method():
        ConstSettings.SCMSettings.MARKET_ALGORITHM = 3
        ConstSettings.SCMSettings.SELF_CONSUMPTION_TYPE = (
            SCMSelfConsumptionType.COLLECTIVE_SELF_CONSUMPTION_SURPLUS_42.value
        )
        ConstSettings.MASettings.MARKET_TYPE = SpotMarketTypeEnum.ONE_SIDED.value

    @staticmethod
    @pytest.fixture()
    def _create_2_house_grid():
        strategy = MagicMock(spec=SCMPVUserProfile)
        strategy.get_energy_to_sell_kWh = MagicMock(return_value=0.5)
        strategy.get_energy_to_buy_kWh = MagicMock(return_value=0.0)
        pv = CoefficientArea(name="pv", strategy=strategy)

        strategy = MagicMock(spec=SCMPVUserProfile)
        strategy.get_energy_to_sell_kWh = MagicMock(return_value=0.2)
        strategy.get_energy_to_buy_kWh = MagicMock(return_value=0.0)
        pv2 = CoefficientArea(name="pv 2", strategy=strategy)

        strategy = MagicMock(spec=SCMLoadHoursStrategy)
        strategy.get_energy_to_sell_kWh = MagicMock(return_value=0.0)
        strategy.get_energy_to_buy_kWh = MagicMock(return_value=0.7)
        load = CoefficientArea(name="load", strategy=strategy)

        strategy = MagicMock(spec=SCMLoadHoursStrategy)
        strategy.get_energy_to_sell_kWh = MagicMock(return_value=0.0)
        strategy.get_energy_to_buy_kWh = MagicMock(return_value=0.1)
        load2 = CoefficientArea(name="load 2", strategy=strategy)
        house1 = CoefficientArea(name="House 1", children=[load, pv])
        house2 = CoefficientArea(name="House 2", children=[load2, pv2])
        area_properties = {
            house1.uuid: {
                SCMPropertyType.AREA_PROPERTIES.name: {
                    "coefficient_percentage": 0.6,
                    "feed_in_tariff": 0.1,
                    "market_maker_rate": 0.3,
                }
            },
            house2.uuid: {
                SCMPropertyType.AREA_PROPERTIES.name: {
                    "coefficient_percentage": 0.4,
                    "feed_in_tariff": 0.05,
                    "market_maker_rate": 0.24,
                }
            },
        }
        house1.update_area_properties(area_properties)
        house2.update_area_properties(area_properties)

        return CoefficientArea(name="Community", children=[house1, house2])

    @staticmethod
    def test_calculate_after_meter_data(_create_2_house_grid):
        grid_area = _create_2_house_grid
        house1 = grid_area.children[0]
        house2 = grid_area.children[1]
        time_slot = now()
        scm = SCMManager(grid_area, time_slot)
        grid_area.calculate_home_after_meter_data(time_slot, scm)
        assert (
            scm._home_data[house1.uuid].area_properties.AREA_PROPERTIES["coefficient_percentage"]
            == 0.6
        )
        assert scm._home_data[house1.uuid].area_properties.AREA_PROPERTIES["feed_in_tariff"] == 0.1
        assert (
            scm._home_data[house1.uuid].area_properties.AREA_PROPERTIES["market_maker_rate"] == 0.3
        )
        assert isclose(scm._home_data[house1.uuid].consumption_kWh, 0.7)
        assert isclose(scm._home_data[house1.uuid].production_kWh, 0.5)
        assert isclose(scm._home_data[house1.uuid].self_consumed_energy_kWh, 0.5)
        assert isclose(scm._home_data[house1.uuid].energy_surplus_kWh, 0.0)
        assert isclose(scm._home_data[house1.uuid].energy_need_kWh, 0.2)

        assert (
            scm._home_data[house2.uuid].area_properties.AREA_PROPERTIES["coefficient_percentage"]
            == 0.4
        )
        assert (
            scm._home_data[house2.uuid].area_properties.AREA_PROPERTIES["feed_in_tariff"] == 0.05
        )
        assert (
            scm._home_data[house2.uuid].area_properties.AREA_PROPERTIES["market_maker_rate"]
            == 0.24
        )
        assert isclose(scm._home_data[house2.uuid].consumption_kWh, 0.1)
        assert isclose(scm._home_data[house2.uuid].production_kWh, 0.2)
        assert isclose(scm._home_data[house2.uuid].self_consumed_energy_kWh, 0.1)
        assert isclose(scm._home_data[house2.uuid].energy_surplus_kWh, 0.1)
        assert isclose(scm._home_data[house2.uuid].energy_need_kWh, 0.0)

    @staticmethod
    def test_calculate_community_after_meter_data(_create_2_house_grid):
        grid_area = _create_2_house_grid
        house1 = grid_area.children[0]
        house2 = grid_area.children[1]
        time_slot = now()
        scm = SCMManager(grid_area, time_slot)
        grid_area.calculate_home_after_meter_data(time_slot, scm)
        scm.calculate_community_after_meter_data()

        assert scm._home_data[house1.uuid].community_total_production_kWh == 0.1
        assert isclose(scm._home_data[house1.uuid].allocated_community_energy_kWh, 0.06)
        assert isclose(scm._home_data[house1.uuid].energy_bought_from_community_kWh, 0.06)
        assert isclose(scm._home_data[house1.uuid].energy_sold_to_grid_kWh, 0.0)

        assert scm._home_data[house2.uuid].community_total_production_kWh == 0.1
        assert isclose(scm._home_data[house2.uuid].allocated_community_energy_kWh, 0.04)
        assert isclose(scm._home_data[house2.uuid].energy_bought_from_community_kWh, 0.00)
        assert isclose(scm._home_data[house2.uuid].energy_sold_to_grid_kWh, 0.04)

        assert scm.community_data.community_uuid == grid_area.uuid
        assert isclose(scm.community_data.production_kWh, 0.7)
        assert isclose(scm.community_data.consumption_kWh, 0.8)
        assert isclose(scm.community_data.energy_need_kWh, 0.2)
        assert isclose(scm.community_data.energy_surplus_kWh, 0.1)
        assert isclose(scm.community_data.self_consumed_energy_kWh, 0.66)
        assert isclose(scm.community_data.energy_bought_from_community_kWh, 0.06)
        assert isclose(scm.community_data.energy_sold_to_grid_kWh, 0.04)

    @staticmethod
    def test_calculate_after_meter_data_including_home_with_single_pv():
        # pylint: disable=too-many-statements
        strategy = MagicMock(spec=SCMLoadHoursStrategy)
        strategy.get_energy_to_sell_kWh = MagicMock(return_value=0.0)
        strategy.get_energy_to_buy_kWh = MagicMock(return_value=0.7)
        load = CoefficientArea(name="load", strategy=strategy)
        house1 = CoefficientArea(name="House 1", children=[load])
        strategy = MagicMock(spec=SCMPVUserProfile)
        strategy.get_energy_to_sell_kWh = MagicMock(return_value=20.0)
        strategy.get_energy_to_buy_kWh = MagicMock(return_value=0.0)
        pv2 = CoefficientArea(name="pv 2", strategy=strategy)
        house2 = CoefficientArea(name="House 2", children=[pv2])
        area_properties = {
            house1.uuid: {
                SCMPropertyType.AREA_PROPERTIES.name: {
                    "coefficient_percentage": 1.0,
                    "feed_in_tariff": 0.1,
                    "market_maker_rate": 0.3,
                }
            },
            house2.uuid: {
                SCMPropertyType.AREA_PROPERTIES.name: {
                    "coefficient_percentage": 0.0,
                    "feed_in_tariff": 0.0,
                    "market_maker_rate": 0.3,
                }
            },
        }
        house1.update_area_properties(area_properties)
        house2.update_area_properties(area_properties)

        grid_area = CoefficientArea(name="Community", children=[house1, house2])

        time_slot = now()
        scm = SCMManager(grid_area, time_slot)
        grid_area.calculate_home_after_meter_data(time_slot, scm)
        scm.calculate_community_after_meter_data()
        grid_area.trigger_energy_trades(scm)
        assert (
            scm._home_data[house1.uuid].area_properties.AREA_PROPERTIES["coefficient_percentage"]
            == 1.0
        )
        assert scm._home_data[house1.uuid].area_properties.AREA_PROPERTIES["feed_in_tariff"] == 0.1
        assert (
            scm._home_data[house1.uuid].area_properties.AREA_PROPERTIES["market_maker_rate"] == 0.3
        )
        assert isclose(scm._home_data[house1.uuid].consumption_kWh, 0.7)
        assert isclose(scm._home_data[house1.uuid].production_kWh, 0.0)
        assert isclose(scm._home_data[house1.uuid].self_consumed_energy_kWh, 0.0)
        assert isclose(scm._home_data[house1.uuid].energy_surplus_kWh, 0.0)
        assert isclose(scm._home_data[house1.uuid].energy_need_kWh, 0.7)

        assert (
            scm._home_data[house2.uuid].area_properties.AREA_PROPERTIES["coefficient_percentage"]
            == 0.0
        )
        assert scm._home_data[house2.uuid].area_properties.AREA_PROPERTIES["feed_in_tariff"] == 0.0
        assert (
            scm._home_data[house2.uuid].area_properties.AREA_PROPERTIES["market_maker_rate"] == 0.3
        )
        assert isclose(scm._home_data[house2.uuid].consumption_kWh, 0.0)
        assert isclose(scm._home_data[house2.uuid].production_kWh, 20.0)
        assert isclose(scm._home_data[house2.uuid].self_consumed_energy_kWh, 0.0)
        assert isclose(scm._home_data[house2.uuid].energy_surplus_kWh, 20.0)
        assert isclose(scm._home_data[house2.uuid].energy_need_kWh, 0.0)
        assert isclose(scm._home_data[house2.uuid].self_production_for_community_kWh, 0.7)

        assert isclose(scm._bills[house1.uuid].base_energy_bill, 0.21)
        assert isclose(scm._bills[house1.uuid].base_energy_bill_excl_revenue, 0.21)
        assert isclose(scm._bills[house1.uuid].base_energy_bill_revenue, 0.0)
        assert isclose(scm._bills[house1.uuid].gsy_energy_bill, 0.21)
        assert isclose(scm._bills[house1.uuid].savings, 0.0)
        assert isclose(scm._bills[house1.uuid].savings_percent, 0.0)
        assert isclose(scm._bills[house1.uuid].home_balance, 0.21)
        assert isclose(scm._bills[house1.uuid].home_balance_kWh, 0.7)
        assert isclose(scm._bills[house2.uuid].export_grid_fees, 0)

        # Validate that the home with the PV populates the energy bills correctly.
        assert isclose(scm._bills[house2.uuid].base_energy_bill, 0.0)
        assert isclose(scm._bills[house2.uuid].base_energy_bill_excl_revenue, 0.0)
        assert isclose(scm._bills[house2.uuid].base_energy_bill_revenue, 0.0)
        assert isclose(scm._bills[house2.uuid].gsy_energy_bill, -0.21)
        assert isclose(scm._bills[house2.uuid].earned_from_community, 0.21)
        assert isclose(scm._bills[house2.uuid].sold_to_community, 0.7)
        assert isclose(scm._bills[house2.uuid].earned_from_grid, 0.0)
        assert isclose(scm._bills[house2.uuid].sold_to_grid, 19.3)
        assert isclose(scm._bills[house2.uuid].home_balance, -0.21)
        assert isclose(scm._bills[house2.uuid].home_balance_kWh, -20.0)
        assert isclose(scm._bills[house2.uuid].export_grid_fees, 0.0)

    @staticmethod
    @pytest.mark.parametrize("intracommunity_base_rate", (None, 0.3))
    def test_trigger_energy_trades(_create_2_house_grid, intracommunity_base_rate):
        original_intracommunity_rate = ConstSettings.SCMSettings.INTRACOMMUNITY_BASE_RATE_EUR
        ConstSettings.SCMSettings.INTRACOMMUNITY_BASE_RATE_EUR = intracommunity_base_rate
        grid_area = _create_2_house_grid
        house1 = grid_area.children[0]
        house2 = grid_area.children[1]
        time_slot = now()
        scm = SCMManager(grid_area, time_slot)
        grid_area.calculate_home_after_meter_data(time_slot, scm)
        scm.calculate_community_after_meter_data()
        grid_area.trigger_energy_trades(scm)

        # energy need * normal market maker fees for the case of positive energy need
        assert isclose(scm._bills[house1.uuid].base_energy_bill, 0.06)
        assert isclose(scm._bills[house1.uuid].base_energy_bill_excl_revenue, 0.06)
        assert isclose(scm._bills[house1.uuid].base_energy_bill_revenue, 0.0)
        assert isclose(scm._bills[house1.uuid].gsy_energy_bill, 0.06)
        assert isclose(scm._bills[house1.uuid].savings, 0.0)
        assert isclose(scm._bills[house1.uuid].savings_percent, 0.0)
        assert isclose(scm._bills[house2.uuid].export_grid_fees, 0.0)
        # energy surplus * feed in tariff for the case of positive energy surplus
        assert isclose(scm._bills[house2.uuid].base_energy_bill, -0.005)
        assert isclose(scm._bills[house2.uuid].base_energy_bill_excl_revenue, 0.0)
        assert isclose(scm._bills[house2.uuid].base_energy_bill_revenue, 0.005)
        if intracommunity_base_rate is None:
            assert isclose(scm._bills[house2.uuid].gsy_energy_bill, -0.0164)
        else:
            assert isclose(scm._bills[house2.uuid].gsy_energy_bill, -0.02)
        assert isclose(scm._bills[house2.uuid].export_grid_fees, 0.0)

        if intracommunity_base_rate is None:
            assert isclose(scm._bills[house2.uuid].savings, 0.0114)
            assert isclose(scm._bills[house2.uuid].savings_percent, 0.0)
        else:
            assert isclose(scm._bills[house2.uuid].savings, 0.015)
            assert isclose(scm._bills[house2.uuid].savings_percent, 0.0)
        assert len(scm._home_data[house1.uuid].trades) == 2
        trades = scm._home_data[house1.uuid].trades
        assert isclose(trades[0].trade_rate, 0.3)
        assert isclose(trades[0].traded_energy, 0.06)
        assert trades[0].seller.name == "Community"
        assert trades[0].buyer.name == "House 1"
        assert isclose(trades[1].trade_rate, 0.3)
        assert isclose(trades[1].traded_energy, 0.14)
        assert trades[1].seller.name == "Grid"
        assert trades[1].buyer.name == "House 1"
        assert len(scm._home_data[house2.uuid].trades) == 2
        trades = scm._home_data[house2.uuid].trades
        if intracommunity_base_rate is None:
            assert isclose(trades[0].trade_rate, 0.24)
        else:
            assert isclose(trades[0].trade_rate, 0.3)
        assert isclose(trades[0].traded_energy, 0.06)
        assert trades[0].seller.name == "House 2"
        assert trades[0].buyer.name == "Community"
        assert isclose(trades[1].trade_rate, 0.05)
        assert isclose(trades[1].traded_energy, 0.04)
        assert trades[1].seller.name == "House 2"
        assert trades[1].buyer.name == "Grid"
        ConstSettings.SCMSettings.INTRACOMMUNITY_BASE_RATE_EUR = original_intracommunity_rate

    @staticmethod
    def test_calculate_energy_benchmark():
        with patch(
            "gsy_e.models.area.scm_manager.AreaEnergyBills.savings_from_buy_from_community", 0.6
        ):
            bills = AreaEnergyBills()
            bills.set_min_max_community_savings(10, 90)
            bills.base_energy_bill_excl_revenue = 1.0
            bills.gsy_energy_bill = 0.4
            assert isclose(bills.savings_percent, 60.0)
            assert isclose(bills.energy_benchmark, (60 - 10) / (90 - 10))

    @staticmethod
    @pytest.fixture()
    def _dynamic_algorithm():
        ConstSettings.SCMSettings.MARKET_ALGORITHM = CoefficientAlgorithm.DYNAMIC.value
        yield
        ConstSettings.SCMSettings.MARKET_ALGORITHM = CoefficientAlgorithm.STATIC.value

    @staticmethod
    def test_change_home_coefficient_percentage(_dynamic_algorithm, _create_2_house_grid):
        grid_area = _create_2_house_grid
        house1 = grid_area.children[0]
        house2 = grid_area.children[1]
        house1.area_properties.AREA_PROPERTIES["coefficient_percentage"] = 0.8
        house2.area_properties.AREA_PROPERTIES["coefficient_percentage"] = 0.2

        time_slot = now()
        scm = SCMManager(grid_area, time_slot)
        scm.community_data.energy_need_kWh = 10
        scm._home_data[house1.uuid] = HomeAfterMeterData(house1.uuid, "house1")
        scm._home_data[house2.uuid] = HomeAfterMeterData(house2.uuid, "house1")
        scm._home_data[house1.uuid].energy_need_kWh = 2
        scm._home_data[house2.uuid].energy_need_kWh = 8
        grid_area.change_home_coefficient_percentage(scm)

        assert house1.area_properties.AREA_PROPERTIES["coefficient_percentage"] == 0.2
        assert house2.area_properties.AREA_PROPERTIES["coefficient_percentage"] == 0.8

        scm._home_data[house1.uuid].energy_need_kWh = 10
        scm._home_data[house2.uuid].energy_need_kWh = 0
        grid_area.change_home_coefficient_percentage(scm)

        assert house1.area_properties.AREA_PROPERTIES["coefficient_percentage"] == 1.0
        assert house2.area_properties.AREA_PROPERTIES["coefficient_percentage"] == 0.0

    @staticmethod
    @pytest.mark.parametrize(
        "scm_setting",
        [
            "coefficient_percentage",
            "market_maker_rate",
            "feed_in_tariff",
        ],
    )
    def test_coefficient_area_only_allows_not_none_values_for_settings(scm_setting):
        strategy = MagicMock(spec=SCMLoadHoursStrategy)
        strategy.get_energy_to_sell_kWh = MagicMock(return_value=0.0)
        strategy.get_energy_to_buy_kWh = MagicMock(return_value=0.7)
        load = CoefficientArea(name="load", strategy=strategy)

        area = CoefficientArea(name="House 1", children=[load])
        scm_settings = {area.uuid: {SCMPropertyType.AREA_PROPERTIES.name: {scm_setting: None}}}
        with pytest.raises(CoefficientAreaException):
            # grid_fee_constant's default value is None, so setting it to 0, it is tested elsewhere
            area.update_area_properties(scm_settings)
        # check does not fail for non-House areas
        house = CoefficientArea(name="House 1", children=[load])
        community = CoefficientArea(name="Community", children=[house])
        scm_settings = {area.uuid: {SCMPropertyType.AREA_PROPERTIES.name: {scm_setting: None}}}
        community.update_area_properties(scm_settings)

    @staticmethod
    def test_update_fee_properties_only_allows_non_none_values():
        strategy = MagicMock(spec=SCMLoadHoursStrategy)
        strategy.get_energy_to_sell_kWh = MagicMock(return_value=0.0)
        strategy.get_energy_to_buy_kWh = MagicMock(return_value=0.7)
        load = CoefficientArea(name="load", strategy=strategy)
        scm_area_uuid = str(uuid.uuid4())
        scm_area = CoefficientArea(name="House 1", children=[load], uuid=scm_area_uuid)

        wrong_scm_properties = {scm_area_uuid: {SCMPropertyType(0).name: {"some_fee": None}}}
        with pytest.raises(CoefficientAreaException):
            scm_area.update_area_properties(wrong_scm_properties)

    @staticmethod
    def test_area_reconfigure_event_triggers_strategy_rea_reconfigure_event():
        strategy = MagicMock(spec=SCMLoadHoursStrategy)
        strategy.get_energy_to_sell_kWh = MagicMock(return_value=0.0)
        strategy.get_energy_to_buy_kWh = MagicMock(return_value=0.7)
        load = CoefficientArea(name="load", strategy=strategy)
        load.area_reconfigure_event()
        load.strategy.area_reconfigure_event.assert_called_once()

    @staticmethod
    def test_virtual_compensation_is_calculated_correctly(_create_2_house_grid):
        grid_area = _create_2_house_grid
        house1 = grid_area.children[0]
        house2 = grid_area.children[1]
        property_dict = {
            house1.uuid: {"GRID_FEES": {"grid_export_fee_const": 0.02}},
            house2.uuid: {"GRID_FEES": {"grid_export_fee_const": 0.02}},
        }
        house1.update_area_properties(property_dict)
        house2.update_area_properties(property_dict)
        house1.area_properties.AREA_PROPERTIES["coefficient_percentage"] = 0.8
        house2.area_properties.AREA_PROPERTIES["coefficient_percentage"] = 0.2
        time_slot = now()
        scm = SCMManager(grid_area, time_slot)
        grid_area.calculate_home_after_meter_data(time_slot, scm)
        scm.calculate_community_after_meter_data()
        grid_area.trigger_energy_trades(scm)

        assert isclose(scm._bills[house1.uuid].export_grid_fees, 0)
        assert isclose(scm._bills[house2.uuid].export_grid_fees, 0.0004)

    @staticmethod
    def test_simplified_self_consumption_energy_results(_create_2_house_grid):
        ConstSettings.SCMSettings.SELF_CONSUMPTION_TYPE = (
            SCMSelfConsumptionType.SIMPLIFIED_COLLECTIVE_SELF_CONSUMPTION_41.value
        )
        grid_area = _create_2_house_grid
        house1 = grid_area.children[0]
        house2 = grid_area.children[1]
        house1.area_properties.AREA_PROPERTIES["coefficient_percentage"] = 0.8
        house2.area_properties.AREA_PROPERTIES["coefficient_percentage"] = 0.2
        time_slot = now()
        scm = SCMManagerWithoutSurplusTrade(grid_area, time_slot)
        production = grid_area.aggregate_production_from_all_homes(time_slot)
        assert production == 0.7
        grid_area.calculate_home_after_meter_data_for_collective_self_consumption(
            time_slot, scm, production
        )

        assert isclose(scm._home_data[house1.uuid].production_kWh, 0.7 * 0.8)
        assert isclose(scm._home_data[house2.uuid].production_kWh, 0.7 * 0.2)

        assert isclose(scm._home_data[house1.uuid].consumption_kWh, 0.7)
        assert isclose(scm._home_data[house2.uuid].consumption_kWh, 0.1)

        assert isclose(scm._home_data[house1.uuid].self_consumed_energy_kWh, 0.7 * 0.8)
        assert isclose(scm._home_data[house2.uuid].self_consumed_energy_kWh, 0.1)

        assert isclose(scm._home_data[house1.uuid].energy_surplus_kWh, 0.0)
        assert isclose(scm._home_data[house2.uuid].energy_surplus_kWh, 0.7 * 0.2 - 0.1)

        assert isclose(scm._home_data[house1.uuid].energy_need_kWh, 0.7 - 0.7 * 0.8)
        assert isclose(scm._home_data[house2.uuid].energy_need_kWh, 0.0)

        assert isclose(scm._home_data[house1.uuid].energy_bought_from_community_kWh, 0.0)
        assert isclose(scm._home_data[house1.uuid].energy_sold_to_grid_kWh, 0.0)
        assert isclose(scm._home_data[house1.uuid].self_production_for_community_kWh, 0.0)
        assert isclose(scm._home_data[house1.uuid].self_production_for_grid_kWh, 0.0)

        assert isclose(scm._home_data[house2.uuid].energy_bought_from_community_kWh, 0.0)
        assert isclose(scm._home_data[house2.uuid].energy_sold_to_grid_kWh, 0.7 * 0.2 - 0.1)
        assert isclose(scm._home_data[house2.uuid].self_production_for_community_kWh, 0.0)
        assert isclose(scm._home_data[house2.uuid].self_production_for_grid_kWh, 0.7 * 0.2 - 0.1)

    @staticmethod
    def test_simplified_self_consumption_bills_results(_create_2_house_grid):
        # pylint: disable=too-many-locals
        ConstSettings.SCMSettings.SELF_CONSUMPTION_TYPE = (
            SCMSelfConsumptionType.SIMPLIFIED_COLLECTIVE_SELF_CONSUMPTION_41.value
        )
        grid_area = _create_2_house_grid
        house1 = grid_area.children[0]
        house2 = grid_area.children[1]
        house1.area_properties.AREA_PROPERTIES["coefficient_percentage"] = 0.8
        house2.area_properties.AREA_PROPERTIES["coefficient_percentage"] = 0.2
        time_slot = now()
        scm = SCMManagerWithoutSurplusTrade(grid_area, time_slot)
        production = grid_area.aggregate_production_from_all_homes(time_slot)
        grid_area.calculate_home_after_meter_data_for_collective_self_consumption(
            time_slot, scm, production
        )
        scm.calculate_community_after_meter_data()
        grid_area.trigger_energy_trades(scm)
        scm.accumulate_community_trades()

        rate_per_kwh1 = scm._bills[house1.uuid].energy_rates.utility_rate
        rate_fees_per_kwh1 = scm._bills[house1.uuid].energy_rates.utility_rate_incl_fees
        monthly_fees1 = scm._bills[house1.uuid].energy_rates.area_fees.total_monthly_fees
        expected_bill1 = 0.7 * rate_fees_per_kwh1 + monthly_fees1
        assert isclose(scm._bills[house1.uuid].base_energy_bill, expected_bill1)
        assert isclose(scm._bills[house1.uuid].base_energy_bill_excl_revenue, expected_bill1)
        assert isclose(scm._bills[house1.uuid].base_energy_bill_revenue, 0.0)
        expected_consumption_from_grid1 = 0.7 - 0.7 * 0.8
        expected_gsy_bill1 = expected_consumption_from_grid1 * rate_fees_per_kwh1 + monthly_fees1
        assert isclose(scm._bills[house1.uuid].gsy_energy_bill, expected_gsy_bill1)
        assert isclose(scm._bills[house1.uuid].gsy_energy_bill_excl_revenue, expected_gsy_bill1)
        assert isclose(scm._bills[house1.uuid].gsy_energy_bill_revenue, 0.0)
        assert isclose(
            scm._bills[house1.uuid].gsy_energy_bill_excl_revenue_without_fees,
            expected_consumption_from_grid1 * rate_fees_per_kwh1,
        )
        assert isclose(
            scm._bills[house1.uuid].gsy_energy_bill_excl_fees,
            expected_consumption_from_grid1 * rate_per_kwh1,
        )

        feed_in_tariff2 = scm._bills[house2.uuid].energy_rates.feed_in_tariff
        rate_fees_per_kwh2 = scm._bills[house2.uuid].energy_rates.utility_rate_incl_fees
        monthly_fees2 = scm._bills[house2.uuid].energy_rates.area_fees.total_monthly_fees
        expected_bill2 = 0.1 * rate_fees_per_kwh2 + monthly_fees2
        assert isclose(scm._bills[house2.uuid].base_energy_bill, expected_bill2)
        assert isclose(scm._bills[house2.uuid].base_energy_bill_excl_revenue, expected_bill2)
        assert isclose(scm._bills[house2.uuid].base_energy_bill_revenue, 0.0)
        expected_production_for_grid2 = 0.7 * 0.2 - 0.1
        expected_gsy_bill2 = -expected_production_for_grid2 * feed_in_tariff2 + monthly_fees2
        assert isclose(scm._bills[house2.uuid].gsy_energy_bill, expected_gsy_bill2)
        assert isclose(scm._bills[house2.uuid].gsy_energy_bill_excl_revenue, monthly_fees2)
        assert isclose(scm._bills[house2.uuid].gsy_energy_bill_revenue, abs(expected_gsy_bill2))
        assert isclose(scm._bills[house2.uuid].gsy_energy_bill_excl_revenue_without_fees, 0.0)
        assert isclose(
            scm._bills[house2.uuid].gsy_energy_bill_excl_fees, expected_gsy_bill2 - monthly_fees2
        )
