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

from types import SimpleNamespace
from unittest.mock import Mock, PropertyMock, patch

import pytest
from gsy_framework.constants_limits import GlobalConfig
from gsy_framework.sim_results.roi.appraisal import calculate_roi
from gsy_framework.sim_results.roi.data_classes import RoiInputs
from gsy_framework.sim_results.roi.parameters import DEFAULT_PARAMETER_SET
from gsy_framework.sim_results.roi.serialization import serialize_result
from pendulum import datetime

from gsy_e.gsy_e_core.sim_results.roi_results_collector import RoiResultsCollector
from gsy_e.models.area import Area
from gsy_e.models.strategy.load_hours import LoadHoursStrategy
from gsy_e.models.strategy.predefined_pv import PVUserProfileStrategy
from gsy_e.models.strategy.pv import PVStrategy
from gsy_e.models.strategy.storage import StorageStrategy

FIRST_SLOT = datetime(2026, 6, 15, 12)
SECOND_SLOT = datetime(2026, 6, 15, 12, 15)
SUPPLIER_RATE = 30
GENERATION_KWH = 2.0
SLOT_LENGTH_SECONDS = 86400


def _trade(seller, buyer, energy, price=0, fee=0, buyer_origin=None, seller_origin=None):
    return SimpleNamespace(
        seller=SimpleNamespace(name=seller, origin=seller_origin or seller),
        buyer=SimpleNamespace(name=buyer, origin=buyer_origin),
        traded_energy=energy,
        trade_price=price,
        fee_price=fee,
    )


def _pv(name, **roi_arguments):
    pv = Area(name, strategy=PVStrategy(capacity_kW=5, **roi_arguments))
    pv.strategy.state.get_energy_production_forecast_kWh = Mock(return_value=GENERATION_KWH)
    return pv


def _record(collector, root, time_slot, trades):
    market = SimpleNamespace(time_slot=time_slot, trades=trades)
    with patch.object(Area, "spot_market", new_callable=PropertyMock, return_value=market):
        collector.update(root)


@pytest.fixture(autouse=True)
def flat_supplier_rate(monkeypatch):
    monkeypatch.setattr(GlobalConfig, "market_maker_rate", SUPPLIER_RATE)


@pytest.fixture(name="house")
def fixture_house():
    house = Area(
        "House 1",
        children=[
            Area("H1 Load", strategy=LoadHoursStrategy(avg_power_W=100)),
            Area(
                "H1 Storage",
                strategy=StorageStrategy(initial_soc=10, battery_capacity_kWh=10),
            ),
            _pv("H1 PV", capital_cost_per_kwp=1200),
        ],
        grid_fee_constant=2,
    )
    return Area("Grid", children=[house], grid_fee_constant=1)


@pytest.fixture(name="community")
def fixture_community():
    return Area(
        "Community",
        children=[
            Area("House 1", children=[Area("H1 Load", strategy=LoadHoursStrategy(avg_power_W=1))]),
            Area("House 2", children=[Area("H2 Load", strategy=LoadHoursStrategy(avg_power_W=1))]),
            _pv("Community PV"),
        ],
    )


def _only_result(collector):
    return next(iter(collector.results(SLOT_LENGTH_SECONDS).values()))


class TestRoiResultsCollector:

    def test_values_each_pv_trade_by_where_its_energy_went(self, house):
        # Given
        collector = RoiResultsCollector()
        trades = [
            _trade("H1 PV", "H1 Load", energy=1.0, price=20),
            _trade("H1 PV", "House 1", energy=0.5, price=10, fee=1, buyer_origin="H2 Load"),
            _trade("H1 PV", "H1 Storage", energy=0.4, price=8),
            _trade("Grid PV", "H1 Load", energy=3.0, price=90),
        ]

        # When
        _record(collector, house, FIRST_SLOT, trades)

        # Then
        result = _only_result(collector)
        expected_inputs = RoiInputs(
            capacity_kwp=5,
            capital_cost_per_kwp=1200,
            ownership_share=1.0,
            avoided_purchase=1.0 * (SUPPLIER_RATE + 3) / 100,
            sales_revenue=(10 - 1) / 100,
            window_generation_kwh=GENERATION_KWH,
            window_days=SLOT_LENGTH_SECONDS / 86400,
        )
        expected = serialize_result(calculate_roi(expected_inputs, DEFAULT_PARAMETER_SET))
        assert result["cash_flow"] == pytest.approx(expected["cash_flow"])
        assert result["self_consumption_ratio"] == pytest.approx(1.0 / GENERATION_KWH)
        assert "capital_cost" not in result["basis"]["inputs_assumed"]

    def test_battery_discharge_is_credited_to_the_pv_after_older_energy(self, house):
        # Given the battery starts with 1 kWh of unknown origin
        collector = RoiResultsCollector()
        _record(collector, house, FIRST_SLOT, [_trade("H1 PV", "H1 Storage", energy=1.0)])

        # When it delivers 1.5 kWh to the load in the next slot
        _record(collector, house, SECOND_SLOT, [_trade("H1 Storage", "H1 Load", energy=1.5)])

        # Then only the 0.5 kWh behind the initial charge came from the PV
        result = _only_result(collector)
        assert result["self_consumption_ratio"] == pytest.approx(0.5 / (2 * GENERATION_KWH))

    def test_a_repeated_update_of_a_slot_does_not_store_energy_twice(self, house):
        # Given
        collector = RoiResultsCollector()
        charge = [_trade("H1 PV", "H1 Storage", energy=1.0)]
        _record(collector, house, FIRST_SLOT, charge)
        _record(collector, house, FIRST_SLOT, charge)

        # When
        _record(collector, house, SECOND_SLOT, [_trade("H1 Storage", "H1 Load", energy=3.0)])

        # Then
        result = _only_result(collector)
        assert result["self_consumption_ratio"] == pytest.approx(1.0 / (2 * GENERATION_KWH))
        assert result["basis"]["window_days"] == pytest.approx(2 * SLOT_LENGTH_SECONDS / 86400)

    def test_annual_generation_annualises_by_season(self, house):
        # Given
        house.children[0].children[2].strategy.roi_inputs = PVStrategy(
            annual_generation_kWh=7000
        ).roi_inputs
        collector = RoiResultsCollector()

        # When
        _record(collector, house, FIRST_SLOT, [])

        # Then
        basis = _only_result(collector)["basis"]
        assert basis["annualisation_factor"] == pytest.approx(7000 / GENERATION_KWH)
        assert basis["seasonally_unadjusted"] is False

    def test_range_brackets_the_central_case(self, house):
        # Given
        collector = RoiResultsCollector()

        # When
        _record(
            collector,
            house,
            FIRST_SLOT,
            [
                _trade("H1 PV", "H1 Load", energy=1.0),
                _trade("H1 PV", "House 1", energy=1.0, price=10, buyer_origin="H2 Load"),
            ],
        )

        # Then
        result = _only_result(collector)
        assert result["range"]["low"]["npv"] < result["npv"] < result["range"]["high"]["npv"]

    def test_shared_pv_gets_a_result_per_member(self, community):
        # Given
        house_1, house_2, pv = community.children
        pv.strategy.roi_inputs = PVStrategy(
            ownership_member_uuids=[house_1.uuid, house_2.uuid], ownership_shares=[0.6, 0.4]
        ).roi_inputs
        collector = RoiResultsCollector()
        trades = [
            _trade("Community PV", "House 1", energy=1.0, buyer_origin="H1 Load"),
            _trade("Community PV", "House 2", energy=0.5, buyer_origin="H2 Load"),
            _trade("Community PV", "Grid", energy=1.0, price=10, buyer_origin="Market Maker"),
        ]

        # When
        _record(collector, community, FIRST_SLOT, trades)

        # Then
        result = _only_result(collector)
        member_1 = result["members"][house_1.uuid]
        expected_inputs = RoiInputs(
            capacity_kwp=5,
            capital_cost_per_kwp=1300,
            ownership_share=0.6,
            avoided_purchase=1.0 * SUPPLIER_RATE / 100,
            sales_revenue=0.6 * 10 / 100,
            window_generation_kwh=GENERATION_KWH,
            window_days=SLOT_LENGTH_SECONDS / 86400,
            benefit_is_apportioned=True,
        )
        expected = serialize_result(calculate_roi(expected_inputs, DEFAULT_PARAMETER_SET))
        assert member_1["cash_flow"] == pytest.approx(expected["cash_flow"])
        assert member_1["basis"]["member_name"] == "House 1"
        assert result["basis"]["ownership_share"] == 1.0

    def test_shares_that_do_not_sum_to_one_withhold_member_results(self, community):
        # Given
        house_1, house_2, pv = community.children
        pv.strategy.roi_inputs = PVStrategy(
            ownership_member_uuids=[house_1.uuid, house_2.uuid], ownership_shares=[0.6, 0.3]
        ).roi_inputs
        collector = RoiResultsCollector()

        # When
        _record(collector, community, FIRST_SLOT, [])

        # Then
        result = _only_result(collector)
        assert "members" not in result
        assert "member_results_withheld" in result["basis"]["flags"]

    def test_profile_pv_takes_its_capacity_from_its_arguments(self):
        # Given / When
        strategy = PVUserProfileStrategy(power_profile={0: 0}, capacity_kW=3.5)

        # Then
        assert strategy.roi_inputs.capacity_kWp == 3.5
