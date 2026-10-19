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
from unittest.mock import Mock, patch

import pytest
from gsy_framework.constants_limits import GlobalConfig
from gsy_framework.exceptions import GSyDeviceException
from gsy_framework.sim_results.roi.appraisal import calculate_roi
from gsy_framework.sim_results.roi.data_classes import RoiInputs
from gsy_framework.sim_results.roi.parameters import DEFAULT_PARAMETER_SET
from gsy_framework.sim_results.roi.serialization import serialize_result
from pendulum import datetime

from gsy_e.gsy_e_core.sim_results.roi_baseline import RoiBaselineError
from gsy_e.gsy_e_core.sim_results.roi_results_collector import RoiResultsCollector
from gsy_e.models.area import Area
from gsy_e.models.strategy.ev_charger import EVChargerStrategy
from gsy_e.models.strategy.external_strategies.pv import (
    PVExternalStrategy,
    PVForecastExternalStrategy,
    PVPredefinedExternalStrategy,
    PVUserProfileExternalStrategy,
)
from gsy_e.models.strategy.load_hours import LoadHoursStrategy
from gsy_e.models.strategy.predefined_pv import PVPredefinedStrategy, PVUserProfileStrategy
from gsy_e.models.strategy.predefined_wind import WindUserProfileStrategy
from gsy_e.models.strategy.pv import PVStrategy
from gsy_e.models.strategy.storage import StorageStrategy

FIRST_SLOT = datetime(2026, 6, 15, 12)
SECOND_SLOT = datetime(2026, 6, 15, 12, 15)
SUPPLIER_RATE = 30
GENERATION_KWH = 2.0
DAY_SECONDS = 86400


class _AssetWithoutType:
    """A strategy that never defines asset_type, as a heat pump does."""

    @property
    def asset_type(self):
        raise NotImplementedError


def _trade(seller, buyer, energy, price=0, fee=0, buyer_origin=None):
    return SimpleNamespace(
        seller=SimpleNamespace(name=seller, uuid=seller, origin=seller, origin_uuid=seller),
        buyer=SimpleNamespace(
            name=buyer, uuid=buyer, origin=buyer_origin, origin_uuid=buyer_origin
        ),
        traded_energy=energy,
        trade_price=price,
        fee_price=fee,
    )


def _pv(name, **roi_arguments):
    pv = Area(name, uuid=name, strategy=PVStrategy(capacity_kW=5, **roi_arguments))
    pv.strategy.state.get_energy_production_forecast_kWh = Mock(return_value=GENERATION_KWH)
    return pv


def _record(collector, root, time_slot, trades_by_area):
    markets = {
        uuid: SimpleNamespace(time_slot=time_slot, trades=trades)
        for uuid, trades in trades_by_area.items()
    }
    markets.setdefault(root.uuid, SimpleNamespace(time_slot=time_slot, trades=[]))
    for area in (root, *root.children):
        if area.children:
            markets.setdefault(area.uuid, SimpleNamespace(time_slot=time_slot, trades=[]))
    with patch.object(Area, "spot_market", property(lambda area: markets.get(area.uuid))):
        collector.update(root)


def _expected_cash_flow(**changes):
    inputs = {
        "capacity_kwp": 5,
        "capital_cost_per_kwp": 1300,
        "ownership_share": 1.0,
        "avoided_purchase": 0.0,
        "sales_revenue": 0.0,
        "window_generation_kwh": GENERATION_KWH,
        "window_days": 1.0,
        **changes,
    }
    result = calculate_roi(RoiInputs(**inputs), DEFAULT_PARAMETER_SET)
    return serialize_result(result)["cash_flow"]


@pytest.fixture(autouse=True)
def flat_supplier_rate(monkeypatch):
    monkeypatch.setattr(GlobalConfig, "market_maker_rate", SUPPLIER_RATE)


@pytest.fixture(name="grid")
def fixture_grid():
    house = Area(
        "House 1",
        uuid="House 1",
        children=[
            Area("H1 Load", uuid="H1 Load", strategy=LoadHoursStrategy(avg_power_W=100)),
            Area("H1 Battery", uuid="H1 Battery", strategy=StorageStrategy()),
            Area("H1 EV", uuid="H1 EV", strategy=EVChargerStrategy()),
            Area("H1 Heat Pump", uuid="H1 Heat Pump", strategy=_AssetWithoutType()),
            _pv("H1 PV", capital_cost_per_kwp=1200),
        ],
        grid_fee_constant=2,
    )
    other_house = Area(
        "House 2",
        uuid="House 2",
        children=[Area("H2 Load", uuid="H2 Load", strategy=LoadHoursStrategy(1))],
    )
    return Area("Grid", uuid="Grid", children=[house, other_house], grid_fee_constant=1)


@pytest.fixture(name="community")
def fixture_community():
    return Area(
        "Community",
        uuid="Community",
        children=[
            Area(
                "House 1",
                uuid="House 1",
                children=[Area("H1 Load", uuid="H1 Load", strategy=LoadHoursStrategy(1))],
            ),
            Area(
                "House 2",
                uuid="House 2",
                children=[Area("H2 Load", uuid="H2 Load", strategy=LoadHoursStrategy(1))],
            ),
            _pv("Community PV", ownership_shares={"House 1": 0.6, "House 2": 0.4}),
        ],
    )


def _community_trades():
    return {
        "Community": [
            _trade("Community PV", "House 1", 1.0, price=20, buyer_origin="H1 Load"),
            _trade("Community PV", "House 2", 0.5, price=10, buyer_origin="H2 Load"),
        ]
    }


def _baseline(**changes):
    paths = ["Community", "Community/House 1", "Community/House 1/H1 Load"]
    paths += ["Community/House 2", "Community/House 2/H2 Load"]
    return {
        "fingerprint": {"areas": {path: {} for path in paths}},
        "area_bills": {"Community/House 1": 0.5, "Community/House 2": 0.3},
        "supplier_rates": {},
        **changes,
    }


def _only_result(collector):
    return next(iter(collector.results(DAY_SECONDS).values()))


class TestOneRunMethod:

    def test_pv_energy_bought_by_any_asset_in_its_area_is_own_use(self, grid):
        # Given
        collector = RoiResultsCollector()
        trades = [
            _trade("H1 PV", "H1 Load", 1.0, price=20),
            _trade("H1 PV", "H1 Battery", 0.4, price=8),
            _trade("H1 PV", "H1 EV", 0.6, price=12),
            _trade("H1 PV", "H1 Heat Pump", 0.5, price=10),
            _trade("H1 PV", "House 1", 0.5, price=10, fee=1, buyer_origin="H2 Load"),
            _trade("Other PV", "H1 Load", 3.0, price=90),
        ]

        # When
        _record(collector, grid, FIRST_SLOT, {"House 1": trades})

        # Then
        result = _only_result(collector)
        assert result["cash_flow"] == pytest.approx(
            _expected_cash_flow(
                capital_cost_per_kwp=1200,
                avoided_purchase=2.5 * (SUPPLIER_RATE + 3) / 100,
                sales_revenue=(10 - 1) / 100,
            )
        )
        assert result["self_consumption_ratio"] == pytest.approx(2.5 / GENERATION_KWH)
        assert result["basis"]["flags"] == ["storage_capex_excluded"]
        assert result["basis"]["baseline_method"] == "analytical"

    def test_a_repeated_slot_is_replaced_and_slots_add_up(self, grid):
        # Given
        collector = RoiResultsCollector()
        trades = {"House 1": [_trade("H1 PV", "H1 Load", 1.0)]}

        # When
        _record(collector, grid, FIRST_SLOT, trades)
        _record(collector, grid, FIRST_SLOT, trades)
        _record(collector, grid, SECOND_SLOT, trades)

        # Then
        result = _only_result(collector)
        assert result["basis"]["window_days"] == pytest.approx(2.0)
        assert result["self_consumption_ratio"] == pytest.approx(2.0 / (2 * GENERATION_KWH))

    def test_a_failure_gives_an_unavailable_result_instead_of_failing_the_run(self, grid):
        # Given
        collector = RoiResultsCollector()
        _record(collector, grid, FIRST_SLOT, {})

        # When
        with patch.object(RoiResultsCollector, "_slot_flows", side_effect=KeyError("boom")):
            _record(collector, grid, SECOND_SLOT, {})

        # Then
        assert _only_result(collector)["unavailable"] == "calculation_failed"

    def test_price_basis_follows_whether_the_supplier_rate_varies(self, grid, monkeypatch):
        # Given
        constant = RoiResultsCollector()
        varying = RoiResultsCollector()

        # When
        _record(constant, grid, FIRST_SLOT, {})
        _record(constant, grid, SECOND_SLOT, {})
        monkeypatch.setattr(GlobalConfig, "market_maker_rate", {FIRST_SLOT: 20, SECOND_SLOT: 40})
        _record(varying, grid, FIRST_SLOT, {})
        _record(varying, grid, SECOND_SLOT, {})

        # Then
        assert _only_result(constant)["basis"]["price_basis"] == "scalar"
        assert _only_result(varying)["basis"]["price_basis"] == "profile"

    def test_shared_pv_without_a_baseline_gets_one_flagged_result(self, community):
        # Given
        collector = RoiResultsCollector()

        # When
        _record(collector, community, FIRST_SLOT, _community_trades())

        # Then
        result = _only_result(collector)
        assert "members" not in result
        assert "shared_asset_estimate" in result["basis"]["flags"]
        assert result["basis"]["baseline_method"] == "analytical"

    def test_wind_turbines_get_no_pv_result(self):
        # Given
        wind = Area("Wind", uuid="Wind", strategy=WindUserProfileStrategy(power_profile={0: 0}))
        grid = Area("Grid", uuid="Grid", children=[Area("Farm", uuid="Farm", children=[wind])])
        collector = RoiResultsCollector()

        # When
        _record(collector, grid, FIRST_SLOT, {})

        # Then
        assert collector.results(DAY_SECONDS) == {}

    def test_capacity_counts_every_panel(self, grid):
        # Given
        pv = grid.children[0].children[4]
        pv.strategy._energy_params.panel_count = 4  # pylint: disable=protected-access
        collector = RoiResultsCollector()

        # When
        _record(collector, grid, FIRST_SLOT, {})

        # Then
        assert _only_result(collector)["basis"]["capacity_kWp"] == 20


class TestTwoRunMethod:

    def test_shared_pv_is_appraised_against_the_baseline_bills(self, community):
        # Given
        collector = RoiResultsCollector(_baseline())

        # When
        _record(collector, community, FIRST_SLOT, _community_trades())

        # Then
        result = _only_result(collector)
        community_benefit = (0.5 - 0.2) + (0.3 - 0.1) + (0 + 0.3)
        assert result["basis"]["baseline_method"] == "simulation"
        assert result["cash_flow"] == pytest.approx(
            _expected_cash_flow(avoided_purchase=community_benefit)
        )
        assert result["members"]["House 1"]["cash_flow"] == pytest.approx(
            _expected_cash_flow(
                avoided_purchase=0.5 - 0.2, ownership_share=0.6, benefit_is_apportioned=True
            )
        )
        assert result["members"]["House 2"]["basis"]["ownership_share"] == 0.4

    def test_a_member_missing_from_the_area_withholds_member_results(self, community):
        # Given
        community.children[2].strategy.roi_inputs = PVStrategy(
            ownership_shares={"House 1": 0.6, "House 9": 0.4}
        ).roi_inputs
        collector = RoiResultsCollector(_baseline())

        # When
        _record(collector, community, FIRST_SLOT, _community_trades())

        # Then
        result = _only_result(collector)
        assert "members" not in result
        assert "member_results_withheld" in result["basis"]["flags"]

    def test_a_different_supplier_rate_stops_the_run(self, community):
        # Given
        baseline = _baseline(supplier_rates={str(FIRST_SLOT): SUPPLIER_RATE + 1})
        collector = RoiResultsCollector(baseline)

        # When / Then
        with pytest.raises(RoiBaselineError, match="supplier rate"):
            _record(collector, community, FIRST_SLOT, {})

    def test_baseline_export_holds_bills_by_name_path(self, community):
        # Given
        collector = RoiResultsCollector()

        # When
        _record(collector, community, FIRST_SLOT, _community_trades())

        # Then
        export = collector.baseline_export({"seed": 7})
        assert export["area_bills"]["Community/House 1"] == pytest.approx(0.2)
        assert export["area_bills"]["Community/Community PV"] == pytest.approx(-0.3)
        assert export["supplier_rates"] == {str(FIRST_SLOT): SUPPLIER_RATE}


class TestPVRoiInputs:

    @pytest.mark.parametrize(
        "arguments",
        [
            {"capital_cost_per_kwp": 0},
            {"capital_cost_per_kwp": -100},
            {"annual_generation_kWh": -1},
            {"ownership_shares": {"House 1": 0.6, "House 2": 0.3}},
            {"ownership_shares": {"House 1": 1.5}},
        ],
    )
    def test_invalid_inputs_stop_the_pv_from_being_built(self, arguments):
        # When / Then
        with pytest.raises(GSyDeviceException):
            PVStrategy(**arguments)

    def test_profile_pv_keeps_its_capacity_through_serialisation(self):
        # Given
        strategy = PVUserProfileStrategy(power_profile={8: 100}, capacity_kW=3.5)

        # When
        restored = PVUserProfileStrategy(
            power_profile={8: 100}, capacity_kW=strategy.serialize()["capacity_kW"]
        )

        # Then
        assert restored.roi_inputs.capacity_kWp == 3.5


@pytest.mark.parametrize(
    "strategy_class",
    [
        PVStrategy,
        PVPredefinedStrategy,
        PVUserProfileStrategy,
        PVExternalStrategy,
        PVPredefinedExternalStrategy,
        PVUserProfileExternalStrategy,
        PVForecastExternalStrategy,
    ],
)
def test_every_pv_strategy_accepts_the_roi_inputs(strategy_class):
    # Given
    profile = {"power_profile": {0: 0}} if "UserProfile" in strategy_class.__name__ else {}

    # When
    strategy = strategy_class(
        capital_cost_per_kwp=1200,
        annual_generation_kWh=5000,
        ownership_shares={"House 1": 1.0},
        **profile,
    )

    # Then
    assert strategy.roi_inputs.capital_cost_per_kwp == 1200
    assert strategy.roi_inputs.annual_generation_kWh == 5000
    assert strategy.roi_inputs.ownership_shares == {"House 1": 1.0}
