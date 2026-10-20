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

import hashlib
import json
import logging
from dataclasses import dataclass, field, fields, replace
from math import isclose
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Iterable, Iterator, List, Optional, Set, Union

from gsy_framework.constants_limits import ConstSettings
from gsy_framework.exceptions import GSyException
from gsy_framework.sim_results.roi.appraisal import calculate_roi
from gsy_framework.sim_results.roi.data_classes import (
    AllocationBasis,
    BaselineMethod,
    PriceBasis,
    RoiFlag,
    RoiInputs,
    SuppressionCause,
)
from gsy_framework.sim_results.roi.parameters import (
    ASSUMED_INPUTS,
    DEFAULT_CAPITAL_COST_PER_KWP,
    DEFAULT_PARAMETER_SET,
    DEFAULT_RANGE_LEVERS,
    OBSERVED_INPUTS,
)
from gsy_framework.sim_results.roi.range import calculate_range
from gsy_framework.sim_results.roi.serialization import serialize_result
from pendulum import DateTime, Duration

import gsy_e.constants
from gsy_e.constants import RandomOrder
from gsy_e.gsy_e_core.util import get_market_maker_rate_from_time_slot
from gsy_e.models.strategy.commercial_producer import CommercialStrategy
from gsy_e.models.strategy.electrolyzer import ElectrolyzerStrategy
from gsy_e.models.strategy.ev_charger import EVChargerStrategy
from gsy_e.models.strategy.predefined_pv import PVUserProfileStrategy
from gsy_e.models.strategy.predefined_wind import WindUserProfileStrategy
from gsy_e.models.strategy.pv import PVStrategy
from gsy_e.models.strategy.storage import StorageStrategy

if TYPE_CHECKING:
    from gsy_e.models.area import Area

log = logging.getLogger(__name__)

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


def _with_text_keys(value):
    if isinstance(value, dict):
        return {str(key): _with_text_keys(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_with_text_keys(item) for item in value]
    return value


def settings_digest(area: "Area") -> Optional[str]:
    """Return a hash of the asset settings, which stays short however long its profiles are."""
    if area.strategy is None:
        return None
    settings = json.dumps(_with_text_keys(area.strategy.serialize()), sort_keys=True, default=str)
    return hashlib.sha256(settings.encode()).hexdigest()


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
        "random_order": gsy_e.constants.RANDOM_ORDER.value,
        "areas": {
            name_path(area): {
                "type": type(area.strategy).__name__ if area.strategy else "Area",
                "grid_fee_constant": area.grid_fee_constant,
                "grid_fee_percentage": area.grid_fee_percentage,
                "settings": settings_digest(area),
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
    if baseline_fingerprint.get("random_order") != RandomOrder.HASH.value:
        problems.append("the baseline was not run with --random-order hash")

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
    for path in sorted(set(areas) & set(baseline_areas)):
        differing = sorted(
            key
            for key in set(areas[path]) | set(baseline_areas[path])
            if areas[path].get(key) != baseline_areas[path].get(key)
        )
        if differing:
            problems.append(f"{path} differs between the two runs in {', '.join(differing)}")
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


@dataclass
class _Flows:
    own_use_kWh: float = 0.0
    avoided_purchase: float = 0.0
    sold_kWh: float = 0.0
    sales_revenue: float = 0.0
    generation_kWh: float = 0.0

    def __add__(self, other: "_Flows") -> "_Flows":
        return _Flows(
            **{
                item.name: getattr(self, item.name) + getattr(other, item.name)
                for item in fields(self)
            }
        )


@dataclass
class _PVRecord:
    name: str
    path: str
    owner_name: str
    capacity_kWp: Optional[float]
    capacity_assumed: bool
    strategy: PVStrategy
    member_paths: Dict[str, str]
    community_paths: Set[str]
    flags: Set[RoiFlag] = field(default_factory=set)
    done: _Flows = field(default_factory=_Flows)
    slot: _Flows = field(default_factory=_Flows)

    @property
    def total(self) -> _Flows:
        return self.done + self.slot


def _leaves(area: "Area") -> Iterator["Area"]:
    for child in area.children:
        if child.children:
            yield from _leaves(child)
        elif child.strategy is not None:
            yield child


def _is_pv(area: "Area") -> bool:
    return isinstance(area.strategy, PVStrategy) and not isinstance(
        area.strategy, WindUserProfileStrategy
    )


def _is_battery(area: "Area") -> bool:
    return isinstance(area.strategy, StorageStrategy) and not isinstance(
        area.strategy, (EVChargerStrategy, ElectrolyzerStrategy)
    )


def _trader_uuid(trader) -> str:
    return trader.origin_uuid or trader.uuid


def _capacity_kWp(strategy: PVStrategy) -> Optional[float]:
    """Return the installed capacity, which the energy parameters hold per panel."""
    if isinstance(strategy, PVUserProfileStrategy) and strategy.capacity_kW is not None:
        return strategy.capacity_kW
    energy_params = strategy._energy_params  # pylint: disable=protected-access
    if getattr(energy_params, "capacity_kW", None) is None:
        return None
    return energy_params.capacity_kW * energy_params.panel_count


class RoiResultsCollector:
    """Collect the RoI inputs of every PV during a run and appraise them when it finishes.

    The owner of a PV is the area that contains it. A PV trade whose buyer is any asset inside
    that area, a battery included, is own use valued at the supplier rate plus the grid fees the
    buyer would otherwise have paid (D7.3 equation 4a). Any other PV trade is revenue (equation
    4b). Each area's net bill in its parent market is kept too, so that a shared PV can be
    appraised against a baseline run without it (D7.3 Section 3.5).

    Totals are kept for completed slots plus the slot in progress, which a repeated publish of
    the same slot replaces, so memory does not grow with the length of the run.
    """

    def __init__(self, baseline: Optional[Dict] = None):
        self._baseline = baseline
        self._records: Dict[str, _PVRecord] = {}
        self._paths: Dict[str, str] = {}
        self._current_slot: Optional[DateTime] = None
        self._completed_slots = 0
        self._done_bills: Dict[str, float] = {}
        self._slot_bills: Dict[str, float] = {}
        self._supplier_rates: Dict[str, float] = {}
        self._failure: Optional[str] = None

    def update(self, root_area: "Area") -> None:
        """Record the current spot market slot, replacing an earlier record of the same slot."""
        try:
            self._update(root_area)
        except RoiBaselineError:
            raise
        except Exception as ex:  # pylint: disable=broad-except
            if self._failure is None:
                log.exception("RoI collection failed, so its results will be unavailable.")
            self._failure = f"collection_failed: {ex}"

    def _update(self, root_area: "Area") -> None:
        if root_area.spot_market is None:
            return
        time_slot = root_area.spot_market.time_slot
        if time_slot != self._current_slot:
            if self._current_slot is not None:
                self._complete_slot()
            self._current_slot = time_slot

        supplier_rate = get_market_maker_rate_from_time_slot(time_slot) or 0.0
        if self._baseline is not None:
            validate_supplier_rate(self._baseline, str(time_slot), supplier_rate)
        self._supplier_rates[str(time_slot)] = supplier_rate

        areas = list(all_areas(root_area))
        self._paths.update({area.uuid: name_path(area) for area in areas})
        self._slot_bills = self._area_bills(areas)
        for leaf in _leaves(root_area):
            if _is_pv(leaf) and leaf.parent.spot_market is not None:
                record = self._record(leaf)
                record.slot = self._slot_flows(leaf, record, supplier_rate)

    def _complete_slot(self) -> None:
        self._completed_slots += 1
        for record in self._records.values():
            record.done = record.total
            record.slot = _Flows()
        for uuid, bill in self._slot_bills.items():
            self._done_bills[uuid] = self._done_bills.get(uuid, 0.0) + bill
        self._slot_bills = {}

    @staticmethod
    def _area_bills(areas: List["Area"]) -> Dict[str, float]:
        """Return what each area paid net in its parent market.

        A market agent trades under its area uuid both in the parent market and in the area's
        own market, so only trades of the market's children count, or the two would cancel.
        """
        bills: Dict[str, float] = {}
        for area in areas:
            if not area.children or area.spot_market is None:
                continue
            children = {child.uuid for child in area.children}
            for trade in area.spot_market.trades:
                if trade.buyer.uuid in children:
                    paid = trade.trade_price / 100.0
                    bills[trade.buyer.uuid] = bills.get(trade.buyer.uuid, 0.0) + paid
                if trade.seller.uuid in children:
                    earned = (trade.trade_price - trade.fee_price) / 100.0
                    bills[trade.seller.uuid] = bills.get(trade.seller.uuid, 0.0) - earned
        return bills

    def _record(self, pv: "Area") -> _PVRecord:
        if pv.uuid not in self._records:
            owner = pv.parent
            shares = pv.strategy.ownership_shares
            candidates = [
                area
                for area in all_areas(owner)
                if area is not owner and area.children and area.name in shares
            ]
            names = [area.name for area in candidates]
            member_paths = {
                area.name: name_path(area) for area in candidates if names.count(area.name) == 1
            }
            capacity = _capacity_kWp(pv.strategy)
            record = _PVRecord(
                name=pv.name,
                path=name_path(pv),
                owner_name=owner.name,
                capacity_kWp=capacity,
                capacity_assumed=capacity is None
                or (
                    isinstance(pv.strategy, PVUserProfileStrategy)
                    and pv.strategy.capacity_kW is None
                ),
                strategy=pv.strategy,
                member_paths=member_paths,
                community_paths={
                    name_path(child)
                    for child in owner.children
                    if not isinstance(child.strategy, CommercialStrategy)
                },
            )
            if set(member_paths) != set(shares):
                record.flags.add(RoiFlag.MEMBER_RESULTS_WITHHELD)
            self._records[pv.uuid] = record
        return self._records[pv.uuid]

    @staticmethod
    def _slot_flows(pv: "Area", record: _PVRecord, supplier_rate: float) -> _Flows:
        owner = pv.parent
        own_leaves = {leaf.uuid: leaf for leaf in _leaves(owner) if leaf.uuid != pv.uuid}
        if any(_is_battery(leaf) for leaf in own_leaves.values()):
            record.flags.add(RoiFlag.STORAGE_CAPEX_EXCLUDED)
        if any(_is_pv(leaf) for leaf in own_leaves.values()):
            record.flags.add(RoiFlag.NOT_SEPARABLE)
        if owner.config.grid_fee_type != 1:
            record.flags.add(RoiFlag.PERCENTAGE_GRID_FEES_EXCLUDED)

        flows = _Flows(
            generation_kWh=pv.strategy.state.get_energy_production_forecast_kWh(
                owner.spot_market.time_slot, 0.0
            )
        )
        for trade in owner.spot_market.trades:
            if trade.seller.uuid != pv.uuid:
                continue
            buyer = own_leaves.get(_trader_uuid(trade.buyer))
            if buyer is not None:
                path_fee = buyer.parent.get_path_to_root_fees()
                flows.own_use_kWh += trade.traded_energy
                flows.avoided_purchase += trade.traded_energy * (supplier_rate + path_fee) / 100.0
            else:
                flows.sold_kWh += trade.traded_energy
                flows.sales_revenue += (trade.trade_price - trade.fee_price) / 100.0
        return flows

    def _bills_by_path(self) -> Dict[str, float]:
        totals = dict(self._done_bills)
        for uuid, bill in self._slot_bills.items():
            totals[uuid] = totals.get(uuid, 0.0) + bill
        return {self._paths[uuid]: bill for uuid, bill in totals.items() if uuid in self._paths}

    def shared_pv_paths(self, root_area: "Area") -> Set[str]:
        """Return the name paths of every PV that has co-owners."""
        return {
            name_path(leaf)
            for leaf in _leaves(root_area)
            if _is_pv(leaf) and leaf.strategy.ownership_shares
        }

    def baseline_export(self, fingerprint: Dict) -> Dict:
        """Return what a later run needs to use this run as its RoI baseline."""
        return {
            "fingerprint": fingerprint,
            "area_bills": self._bills_by_path(),
            "supplier_rates": dict(self._supplier_rates),
        }

    def results(self, slot_length: Duration) -> Dict:
        """Return the serialised RoI result of every PV, keyed by its uuid."""
        window_days = ((self._completed_slots + 1) * slot_length).total_days()
        baseline_paths = (
            set(self._baseline["fingerprint"]["areas"]) if self._baseline is not None else None
        )
        bills = self._bills_by_path() if self._baseline is not None else {}
        results = {}
        for uuid, record in self._records.items():
            try:
                if self._failure is not None:
                    raise RuntimeError(self._failure)
                uses_baseline = (
                    baseline_paths is not None
                    and bool(record.strategy.ownership_shares)
                    and record.path not in baseline_paths
                )
                results[uuid] = self._pv_result(record, window_days, uses_baseline, bills)
            except Exception as ex:  # pylint: disable=broad-except
                log.exception("RoI appraisal of %s failed.", record.name)
                results[uuid] = {
                    "unavailable": SuppressionCause.CALCULATION_FAILED.value,
                    "error": str(ex),
                }
        return results

    def _pv_result(
        self, record: _PVRecord, window_days: float, uses_baseline: bool, bills: Dict[str, float]
    ) -> Dict:
        strategy = record.strategy
        flows = record.total
        inputs = RoiInputs(
            capacity_kWp=record.capacity_kWp or 0.0,
            capital_cost_per_kWp=strategy.capital_cost_per_kWp or DEFAULT_CAPITAL_COST_PER_KWP,
            ownership_share=1.0,
            avoided_purchase=flows.avoided_purchase,
            sales_revenue=flows.sales_revenue,
            window_generation_kWh=flows.generation_kWh,
            window_days=window_days,
            annual_generation_kWh=strategy.annual_generation_kWh,
        )
        flags = set(record.flags)
        if uses_baseline:
            baseline_bills = self._baseline["area_bills"]
            community_benefit = sum(
                baseline_bills.get(path, 0.0) - bills.get(path, 0.0)
                for path in record.community_paths
            )
            inputs = replace(inputs, avoided_purchase=community_benefit - flows.sales_revenue)
        elif strategy.ownership_shares:
            flags.add(RoiFlag.SHARED_ASSET_ESTIMATE)

        basis = self._basis(record, inputs, flags, uses_baseline)
        result = self._appraise(inputs, flows.own_use_kWh, flows.sold_kWh)
        result["basis"].update(basis)
        if uses_baseline and RoiFlag.MEMBER_RESULTS_WITHHELD not in flags:
            result["members"] = {
                name: self._member_result(record, inputs, flows, basis, bills, name, share)
                for name, share in strategy.ownership_shares.items()
            }
        return result

    def _member_result(
        self,
        record: _PVRecord,
        inputs: RoiInputs,
        flows: _Flows,
        basis: Dict,
        bills: Dict[str, float],
        name: str,
        share: float,
    ) -> Dict:
        path = record.member_paths[name]
        member_inputs = replace(
            inputs,
            ownership_share=share,
            benefit_is_apportioned=True,
            avoided_purchase=self._baseline["area_bills"].get(path, 0.0) - bills.get(path, 0.0),
            sales_revenue=share * flows.sales_revenue,
        )
        result = self._appraise(member_inputs, share * flows.own_use_kWh, share * flows.sold_kWh)
        result["basis"].update(
            {**basis, "ownership_share": share, "member_name": name, "member_path": path}
        )
        return result

    @staticmethod
    def _appraise(inputs: RoiInputs, own_use_kWh: float, sold_kWh: float) -> Dict:
        result = serialize_result(calculate_roi(inputs, DEFAULT_PARAMETER_SET))
        result["self_consumption_ratio"] = (
            own_use_kWh / inputs.window_generation_kWh
            if inputs.window_generation_kWh > 0
            else None
        )
        if result["unavailable"] is None:
            cases = calculate_range(
                inputs, DEFAULT_PARAMETER_SET, DEFAULT_RANGE_LEVERS, own_use_kWh, sold_kWh
            )
            result["range"] = {case: serialize_result(roi) for case, roi in cases.items()}
        return result

    def _basis(
        self, record: _PVRecord, inputs: RoiInputs, flags: Set[RoiFlag], uses_baseline: bool
    ) -> Dict:
        assumed: List[str] = list(ASSUMED_INPUTS)
        observed: List[str] = list(OBSERVED_INPUTS)
        if record.strategy.capital_cost_per_kWp is None:
            assumed.append("capital_cost")
        (assumed if record.capacity_assumed else observed).append("capacity")
        rates = set(self._supplier_rates.values())
        return {
            "baseline_method": (
                BaselineMethod.SIMULATION if uses_baseline else BaselineMethod.ANALYTICAL
            ).value,
            "allocation_basis": AllocationBasis.MARKET_CLEARING.value,
            "price_basis": (PriceBasis.PROFILE if len(rates) > 1 else PriceBasis.SCALAR).value,
            "window_start": min(self._supplier_rates) if self._supplier_rates else None,
            "window_days": inputs.window_days,
            "window_is_metered": False,
            "ownership_share": inputs.ownership_share,
            "capacity_kWp": inputs.capacity_kWp,
            "capital_cost_per_kWp": inputs.capital_cost_per_kWp,
            "annual_generation_kWh": inputs.annual_generation_kWh,
            "asset_name": record.name,
            "owner_name": record.owner_name,
            "last_realised_year": None,
            "inputs_observed": observed,
            "inputs_assumed": assumed,
            "flags": sorted(flag.value for flag in flags),
        }
