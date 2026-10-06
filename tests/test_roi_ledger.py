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

from gsy_e.gsy_e_core.sim_results.roi_ledger import RoiLedger
from gsy_e.models.area import Area
from gsy_e.models.strategy.load_hours import LoadHoursStrategy
from gsy_e.models.strategy.predefined_pv import PVUserProfileStrategy
from gsy_e.models.strategy.pv import PVStrategy
from gsy_e.models.strategy.storage import StorageStrategy

SLOT = datetime(2026, 6, 15, 12)
SUPPLIER_RATE = 30
GENERATION_KWH = 2.0
QUARTER_HOUR_SECONDS = 900


def _trade(seller, buyer, energy, price, fee, buyer_origin=None):
    return SimpleNamespace(
        seller=SimpleNamespace(name=seller, origin=seller),
        buyer=SimpleNamespace(name=buyer, origin=buyer_origin),
        traded_energy=energy,
        trade_price=price,
        fee_price=fee,
    )


@pytest.fixture(name="grid")
def fixture_grid(monkeypatch):
    monkeypatch.setattr(GlobalConfig, "market_maker_rate", SUPPLIER_RATE)
    pv = Area("H1 PV", strategy=PVStrategy(capacity_kW=5, capital_cost_per_kwp=1200))
    pv.strategy.state.get_energy_production_forecast_kWh = Mock(return_value=GENERATION_KWH)
    house = Area(
        "House 1",
        children=[
            Area("H1 Load", strategy=LoadHoursStrategy(avg_power_W=100)),
            Area("H1 Storage", strategy=StorageStrategy()),
            pv,
        ],
        grid_fee_constant=2,
    )
    return Area("Grid", children=[house], grid_fee_constant=1)


def _record_slot(grid, trades):
    market = SimpleNamespace(time_slot=SLOT, trades=trades)
    ledger = RoiLedger()
    with patch.object(Area, "spot_market", new_callable=PropertyMock, return_value=market):
        ledger.update(grid)
    return ledger


class TestRoiLedger:

    def test_values_each_pv_trade_by_where_its_energy_went(self, grid):
        # Given
        trades = [
            _trade("H1 PV", "H1 Load", energy=1.0, price=20, fee=0),
            _trade("H1 PV", "House 1", energy=0.5, price=10, fee=1, buyer_origin="H2 Load"),
            _trade("H1 PV", "H1 Storage", energy=0.4, price=8, fee=0),
            _trade("Grid PV", "H1 Load", energy=3.0, price=90, fee=0),
        ]

        # When
        result = _record_slot(grid, trades).results(QUARTER_HOUR_SECONDS)

        # Then
        pv_result = next(iter(result.values()))
        expected_inputs = RoiInputs(
            capacity_kwp=5,
            capital_cost_per_kwp=1200,
            ownership_share=1.0,
            avoided_purchase=1.0 * (SUPPLIER_RATE + 3) / 100,
            sales_revenue=(10 - 1) / 100,
            window_generation_kwh=GENERATION_KWH,
            window_days=QUARTER_HOUR_SECONDS / 86400,
        )
        expected = serialize_result(calculate_roi(expected_inputs, DEFAULT_PARAMETER_SET))
        assert pv_result["cash_flow"] == pytest.approx(expected["cash_flow"])
        assert pv_result["self_consumption_ratio"] == pytest.approx(1.0 / GENERATION_KWH)
        assert pv_result["basis"]["flags"] == ["storage_attribution_excluded"]
        assert "capital_cost" not in pv_result["basis"]["inputs_assumed"]

    def test_a_repeated_update_of_a_slot_replaces_it(self, grid):
        # Given
        trades = [_trade("H1 PV", "H1 Load", energy=1.0, price=20, fee=0)]
        market = SimpleNamespace(time_slot=SLOT, trades=trades)
        ledger = RoiLedger()

        # When
        with patch.object(Area, "spot_market", new_callable=PropertyMock, return_value=market):
            ledger.update(grid)
            ledger.update(grid)

        # Then
        basis = next(iter(ledger.results(QUARTER_HOUR_SECONDS).values()))["basis"]
        assert basis["window_days"] == pytest.approx(QUARTER_HOUR_SECONDS / 86400)

    def test_missing_capital_cost_uses_the_default_and_says_so(self, grid):
        # Given
        grid.children[0].children[2].strategy.capital_cost_per_kwp = None

        # When
        result = _record_slot(grid, []).results(QUARTER_HOUR_SECONDS)

        # Then
        basis = next(iter(result.values()))["basis"]
        assert basis["capital_cost_per_kwp"] == 1300
        assert "capital_cost" in basis["inputs_assumed"]

    def test_profile_pv_takes_its_capacity_from_the_roi_argument(self):
        # Given
        strategy = PVUserProfileStrategy(power_profile={0: 0}, capacity_kW=3.5)

        # When / Then
        assert strategy.roi_capacity_kW == 3.5
