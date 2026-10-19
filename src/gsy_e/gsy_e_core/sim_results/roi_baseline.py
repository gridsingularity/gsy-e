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
from math import isclose
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Iterable, Iterator, List, Union

from gsy_framework.constants_limits import ConstSettings
from gsy_framework.exceptions import GSyException

import gsy_e.constants

if TYPE_CHECKING:
    from gsy_e.models.area import Area

BASELINE_FILE_NAME = "roi_baseline.json"


class RoiBaselineError(GSyException):
    """Raised when the baseline run cannot be compared with this run, listing every reason."""

    def __init__(self, problems: List[str]):
        self.problems = problems
        super().__init__("Invalid RoI baseline run: " + "; ".join(problems))


def name_path(area: "Area") -> str:
    """Return the names from the root to the area, which stay the same across two runs."""
    names = []
    while area is not None:
        names.append(area.name)
        area = area.parent
    return "/".join(reversed(names))


def all_areas(area: "Area") -> Iterator["Area"]:
    """Yield the area and every area below it."""
    yield area
    for child in area.children:
        yield from all_areas(child)


def run_fingerprint(root_area: "Area", seed: int) -> Dict:
    """Return the properties that two runs must share for their bills to be comparable."""
    config = root_area.config
    return {
        "seed": None if seed in (None, "") else int(seed),
        "start_date": str(config.start_date),
        "sim_duration_seconds": config.sim_duration.total_seconds(),
        "slot_length_seconds": config.slot_length.total_seconds(),
        "tick_length_seconds": config.tick_length.total_seconds(),
        "market_type": ConstSettings.MASettings.MARKET_TYPE,
        "bid_offer_match_type": ConstSettings.MASettings.BID_OFFER_MATCH_TYPE,
        "grid_fee_type": config.grid_fee_type,
        "ordered_by_item": gsy_e.constants.ORDER_BY_ITEM_HASH,
        "areas": {
            name_path(area): {
                "type": type(area.strategy).__name__ if area.strategy else "Area",
                "grid_fee_constant": area.grid_fee_constant,
                "grid_fee_percentage": area.grid_fee_percentage,
            }
            for area in all_areas(root_area)
        },
    }


def load_baseline(source: Union[str, Path, Dict]) -> Dict:
    """Return the baseline from a dict, a roi_baseline.json file or an export folder."""
    if isinstance(source, dict):
        return source
    path = Path(source)
    if path.is_dir():
        matches = sorted(path.rglob(BASELINE_FILE_NAME))
        if len(matches) != 1:
            raise RoiBaselineError(
                [f"expected one {BASELINE_FILE_NAME} under {path}, found {len(matches)}"]
            )
        path = matches[0]
    if not path.is_file():
        raise RoiBaselineError([f"{path} does not exist"])
    with open(path, encoding="utf-8") as baseline_file:
        return json.load(baseline_file)


def validate_fingerprint(
    baseline: Dict, fingerprint: Dict, shared_pv_paths: Iterable[str]
) -> List[str]:
    """Return every reason why the baseline run is not this run without its shared PVs."""
    baseline_fingerprint = baseline.get("fingerprint", {})
    problems = [
        f"{key} is {baseline_fingerprint.get(key)!r} in the baseline and {value!r} in this run"
        for key, value in fingerprint.items()
        if key != "areas" and baseline_fingerprint.get(key) != value
    ]
    if not baseline_fingerprint.get("ordered_by_item"):
        problems.append("the baseline was not run with per-item ordering (--roi-comparable)")

    baseline_areas = baseline_fingerprint.get("areas", {})
    areas = fingerprint["areas"]
    removed = set(areas) - set(baseline_areas)
    problems.extend(
        f"{path} is in the baseline but not in this run"
        for path in sorted(set(baseline_areas) - set(areas))
    )
    problems.extend(
        f"{path} is missing from the baseline but is not a shared PV"
        for path in sorted(removed - set(shared_pv_paths))
    )
    if not removed:
        problems.append("the baseline has every area of this run, so no shared PV was removed")
    problems.extend(
        f"{path} differs between the runs: {baseline_areas[path]} against {areas[path]}"
        for path in sorted(set(areas) & set(baseline_areas))
        if baseline_areas[path] != areas[path]
    )
    return problems


def validate_supplier_rate(baseline: Dict, time_slot: str, rate: float) -> None:
    """Raise when the supplier rate of a slot differs from the baseline run."""
    baseline_rate = baseline.get("supplier_rates", {}).get(time_slot)
    if baseline_rate is not None and not isclose(baseline_rate, rate):
        raise RoiBaselineError(
            [
                f"the supplier rate at {time_slot} is {baseline_rate} in the baseline "
                f"and {rate} in this run"
            ]
        )
