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
from copy import deepcopy

import pytest

import gsy_e.constants
from gsy_e.constants import RandomOrder
from gsy_e.gsy_e_core.sim_results.endpoint_buffer import SimulationEndpointBuffer
from gsy_e.gsy_e_core.sim_results.roi_results_collector import (
    BASELINE_FILE_NAME,
    RoiBaselineError,
    load_baseline,
    run_fingerprint,
    validate_fingerprint,
)
from gsy_e.models.area import Area
from gsy_e.models.strategy.load_hours import LoadHoursStrategy
from gsy_e.models.strategy.pv import PVStrategy

SHARED_PV = "Community/Community PV"


@pytest.fixture(name="community")
def fixture_community(monkeypatch):
    monkeypatch.setattr(gsy_e.constants, "RANDOM_ORDER", RandomOrder.HASH)
    return Area(
        "Community",
        children=[
            Area("House 1", children=[Area("H1 Load", strategy=LoadHoursStrategy(1))]),
            Area(
                "Community PV",
                strategy=PVStrategy(capacity_kW=5, ownership_shares={"House 1": 1.0}),
            ),
        ],
    )


def _baseline_of(community):
    fingerprint = deepcopy(run_fingerprint(community, 7))
    del fingerprint["areas"][SHARED_PV]
    return {"fingerprint": fingerprint, "area_bills": {}, "supplier_rates": {}}


class TestValidateFingerprint:

    def test_the_same_run_without_the_shared_pv_is_valid(self, community):
        # When
        problems = validate_fingerprint(
            _baseline_of(community), run_fingerprint(community, 7), {SHARED_PV}
        )

        # Then
        assert problems == []

    def test_every_mismatch_is_listed(self, community):
        # Given
        baseline = _baseline_of(community)
        baseline["fingerprint"]["random_order"] = RandomOrder.SHARED.value
        baseline["fingerprint"]["areas"]["Community/House 2"] = {"type": "Area"}

        # When
        problems = validate_fingerprint(baseline, run_fingerprint(community, 8), {SHARED_PV})

        # Then
        assert any(problem.startswith("seed") for problem in problems)
        assert any("--random-order hash" in problem for problem in problems)
        assert any("House 2 is in the baseline" in problem for problem in problems)

    def test_a_removed_area_must_be_a_shared_pv(self, community):
        # Given
        baseline = _baseline_of(community)
        del baseline["fingerprint"]["areas"]["Community/House 1/H1 Load"]

        # When
        problems = validate_fingerprint(baseline, run_fingerprint(community, 7), {SHARED_PV})

        # Then
        assert problems == [
            "Community/House 1/H1 Load is missing from the baseline but is not a shared PV"
        ]

    def test_a_baseline_with_every_area_removes_no_shared_pv(self, community):
        # Given
        fingerprint = run_fingerprint(community, 7)
        baseline = {"fingerprint": deepcopy(fingerprint)}

        # When
        problems = validate_fingerprint(baseline, fingerprint, {SHARED_PV})

        # Then
        assert problems == ["the baseline has every area of this run, so no shared PV was removed"]


class TestLoadBaseline:

    def test_loads_from_an_export_folder(self, tmp_path):
        # Given
        nested = tmp_path / "2026-10-19T10:00:00" / "aggregated_results"
        nested.mkdir(parents=True)
        (nested / BASELINE_FILE_NAME).write_text(json.dumps({"area_bills": {"A": 1.0}}))

        # When / Then
        assert load_baseline(str(tmp_path)) == {"area_bills": {"A": 1.0}}

    def test_a_missing_baseline_stops_the_run(self, tmp_path):
        # When / Then
        with pytest.raises(RoiBaselineError):
            load_baseline(str(tmp_path / "missing.json"))


def test_an_invalid_baseline_stops_the_run_before_its_first_slot(community):
    # Given
    baseline = _baseline_of(community)
    baseline["fingerprint"]["seed"] = 1

    # When / Then
    with pytest.raises(RoiBaselineError, match="seed"):
        SimulationEndpointBuffer("job", 7, community, False, roi_baseline=baseline)
