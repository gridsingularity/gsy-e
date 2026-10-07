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

from collections import deque
from copy import deepcopy
from dataclasses import dataclass, field, replace
from math import isclose
from typing import TYPE_CHECKING, Deque, Dict, Iterator, List, Optional, Set

from gsy_framework.constants_limits import GlobalConfig
from gsy_framework.sim_results.roi.appraisal import calculate_roi
from gsy_framework.sim_results.roi.data_classes import RangeLevers, RoiInputs, RoiParameterSet
from gsy_framework.sim_results.roi.parameters import (
    DEFAULT_CAPITAL_COST_PER_KWP,
    DEFAULT_PARAMETER_SET,
    DEFAULT_RANGE_LEVERS,
)
from gsy_framework.sim_results.roi.range import calculate_range
from gsy_framework.sim_results.roi.serialization import serialize_result
from pendulum import DateTime

from gsy_e.gsy_e_core.util import get_market_maker_rate_from_time_slot
from gsy_e.models.base import AssetType
from gsy_e.models.strategy.pv import PVStrategy
from gsy_e.models.strategy.smart_meter import SmartMeterStrategy
from gsy_e.models.strategy.storage import StorageStrategy

if TYPE_CHECKING:
    from gsy_e.models.area import Area

CENTS_PER_CURRENCY_UNIT = 100
CONSTANT_GRID_FEE_TYPE = 1
SECONDS_PER_DAY = 86400
INITIAL_CHARGE = "initial charge"
OTHER_SOURCE = "other source"

ASSUMED_INPUTS = [
    "capital_cost",
    "operating_cost",
    "degradation",
    "retail_escalation",
    "export_escalation",
    "discount_rate",
    "replacement_year",
    "replacement_cost",
]
OBSERVED_INPUTS = ["capacity", "ledger_flows", "generation", "self_consumption_ratio"]


@dataclass
class _Flows:
    own_consumption_kWh: float = 0.0
    avoided_purchase: float = 0.0
    sold_kWh: float = 0.0
    sales_revenue: float = 0.0
    generation_kWh: float = 0.0
    member_own_consumption_kWh: Dict[str, float] = field(default_factory=dict)
    member_avoided_purchase: Dict[str, float] = field(default_factory=dict)

    def add_own_consumption(self, energy_kWh: float, value: float, member: Optional[str]):
        self.own_consumption_kWh += energy_kWh
        self.avoided_purchase += value
        if member is not None:
            self.member_own_consumption_kWh[member] = (
                self.member_own_consumption_kWh.get(member, 0.0) + energy_kWh
            )
            self.member_avoided_purchase[member] = (
                self.member_avoided_purchase.get(member, 0.0) + value
            )


class _StoredEnergy:
    """Energy held by one battery, oldest first, labelled with the asset that supplied it."""

    def __init__(self, initial_kWh: float):
        self._blocks: Deque[List] = deque()
        if initial_kWh > 0:
            self._blocks.append([INITIAL_CHARGE, initial_kWh])

    def charge(self, source: str, energy_kWh: float) -> None:
        self._blocks.append([source, energy_kWh])

    def discharge(self, energy_kWh: float) -> Dict[str, float]:
        drawn: Dict[str, float] = {}
        while energy_kWh > 0 and self._blocks:
            source, available_kWh = self._blocks[0]
            taken_kWh = min(available_kWh, energy_kWh)
            drawn[source] = drawn.get(source, 0.0) + taken_kWh
            energy_kWh -= taken_kWh
            if taken_kWh == available_kWh:
                self._blocks.popleft()
            else:
                self._blocks[0][1] = available_kWh - taken_kWh
        return drawn

    def self_discharge(self, fraction: float) -> None:
        for block in self._blocks:
            block[1] *= 1 - fraction


@dataclass
class _PVRecord:
    name: str
    owner_name: str
    capacity_kWp: Optional[float]
    strategy: PVStrategy
    member_names: Dict[str, str]
    slots: Dict[DateTime, _Flows] = field(default_factory=dict)
    flags: Set[str] = field(default_factory=set)


def _leaves(area: "Area") -> Iterator["Area"]:
    for child in area.children:
        if child.children:
            yield from _leaves(child)
        elif child.strategy is not None:
            yield child


def _is_consumer(area: "Area") -> bool:
    return (
        isinstance(area.strategy, SmartMeterStrategy)
        or area.strategy.asset_type is AssetType.CONSUMER
    )


def _member_of(area: "Area", owner: "Area", member_uuids: Set[str]) -> Optional[str]:
    while area is not None and area is not owner:
        if area.uuid in member_uuids:
            return area.uuid
        area = area.parent
    return None


def _capacity_kWp(strategy: PVStrategy) -> Optional[float]:
    if strategy.roi_inputs.capacity_kWp is not None:
        return strategy.roi_inputs.capacity_kWp
    return getattr(strategy._energy_params, "capacity_kW", None)  # pylint: disable=W0212


class RoiResultsCollector:
    """Collect, per PV and market slot, the totals of the trade-based RoI baseline.

    The owner of a PV is the area that contains it. Energy that reaches a consumer inside that
    area, directly or through a battery in it, is valued at the supplier rate plus the grid fees
    the consumer would otherwise have paid (D7.3 equation 4a). Energy sold outside the area is
    revenue (equation 4b). Battery energy is followed oldest first, so a discharge is credited
    to the PV whose energy was stored earliest.
    """

    def __init__(self):
        self._records: Dict[str, _PVRecord] = {}
        self._current_slot: Optional[DateTime] = None
        self._stored_before_slot: Dict[str, _StoredEnergy] = {}
        self._stored_after_slot: Dict[str, _StoredEnergy] = {}

    def update(self, root_area: "Area") -> None:
        """Record the current spot market slot, replacing an earlier record of the same slot."""
        leaves = list(_leaves(root_area))
        pvs = [leaf for leaf in leaves if isinstance(leaf.strategy, PVStrategy)]
        markets = [pv.parent.spot_market for pv in pvs if pv.parent.spot_market is not None]
        if not markets:
            return
        time_slot = markets[0].time_slot
        if time_slot != self._current_slot:
            self._stored_before_slot = self._stored_after_slot
            self._current_slot = time_slot
        stored = deepcopy(self._stored_before_slot)

        flows = {pv.uuid: self._direct_flows(pv, time_slot) for pv in pvs if pv.parent.spot_market}
        pv_by_name = {pv.name: pv for pv in pvs if pv.uuid in flows}
        for battery in leaves:
            if isinstance(battery.strategy, StorageStrategy) and battery.parent.spot_market:
                self._battery_flows(battery, stored, pv_by_name, flows, time_slot)
        self._stored_after_slot = stored

        for pv in pv_by_name.values():
            self._record(pv).slots[time_slot] = flows[pv.uuid]

    def results(
        self,
        slot_length_seconds: float,
        parameters: RoiParameterSet = None,
        range_levers: RangeLevers = None,
    ) -> Dict:
        """Return the serialised RoI result of every PV, keyed by its uuid."""
        parameters = parameters or DEFAULT_PARAMETER_SET
        range_levers = range_levers or DEFAULT_RANGE_LEVERS
        return {
            uuid: self._pv_result(record, slot_length_seconds, parameters, range_levers)
            for uuid, record in self._records.items()
            if record.slots
        }

    def _record(self, pv: "Area") -> _PVRecord:
        if pv.uuid not in self._records:
            roi_inputs = pv.strategy.roi_inputs
            members = set(roi_inputs.ownership_member_uuids)
            self._records[pv.uuid] = _PVRecord(
                name=pv.name,
                owner_name=pv.parent.name,
                capacity_kWp=_capacity_kWp(pv.strategy),
                strategy=pv.strategy,
                member_names={
                    area.uuid: area.name
                    for area in self._areas_under(pv.parent)
                    if area.uuid in members
                },
            )
        return self._records[pv.uuid]

    @staticmethod
    def _areas_under(area: "Area") -> Iterator["Area"]:
        for child in area.children:
            yield child
            yield from RoiResultsCollector._areas_under(child)

    @staticmethod
    def _avoided_purchase(consumer: "Area", energy_kWh: float, time_slot: DateTime) -> float:
        supplier_rate = get_market_maker_rate_from_time_slot(time_slot) or 0
        path_fee = consumer.parent.get_path_to_root_fees()
        return energy_kWh * (supplier_rate + path_fee) / CENTS_PER_CURRENCY_UNIT

    def _direct_flows(self, pv: "Area", time_slot: DateTime) -> _Flows:
        owner = pv.parent
        record = self._record(pv)
        member_uuids = set(record.member_names)
        consumers = {leaf.name: leaf for leaf in _leaves(owner) if _is_consumer(leaf)}
        batteries = {
            leaf.name for leaf in _leaves(owner) if isinstance(leaf.strategy, StorageStrategy)
        }
        if sum(isinstance(leaf.strategy, PVStrategy) for leaf in _leaves(owner)) > 1:
            record.flags.add("not_separable")
        if owner.config.grid_fee_type != CONSTANT_GRID_FEE_TYPE:
            record.flags.add("percentage_grid_fees_excluded")

        flows = _Flows(
            generation_kWh=pv.strategy.state.get_energy_production_forecast_kWh(time_slot, 0.0)
        )
        for trade in owner.spot_market.trades:
            if trade.seller.name != pv.name:
                continue
            buyer = trade.buyer.origin or trade.buyer.name
            if buyer in consumers:
                flows.add_own_consumption(
                    trade.traded_energy,
                    self._avoided_purchase(consumers[buyer], trade.traded_energy, time_slot),
                    _member_of(consumers[buyer], owner, member_uuids),
                )
            elif buyer not in batteries:
                flows.sold_kWh += trade.traded_energy
                flows.sales_revenue += (
                    trade.trade_price - trade.fee_price
                ) / CENTS_PER_CURRENCY_UNIT
        return flows

    def _battery_flows(
        self,
        battery: "Area",
        stored: Dict[str, _StoredEnergy],
        pv_by_name: Dict[str, "Area"],
        flows: Dict[str, _Flows],
        time_slot: DateTime,
    ) -> None:
        state = battery.strategy.state
        losses = state.losses
        energy = stored.setdefault(battery.uuid, _StoredEnergy(state.initial_capacity_kWh))
        kept_on_charge = 1 - losses.charging_loss_percent / 100
        kept_on_discharge = 1 - losses.discharging_loss_percent / 100

        for trade in battery.parent.spot_market.trades:
            if trade.buyer.name == battery.name:
                source = trade.seller.origin or trade.seller.name
                energy.charge(
                    source if source in pv_by_name else OTHER_SOURCE,
                    trade.traded_energy * kept_on_charge,
                )
            elif trade.seller.name == battery.name and kept_on_discharge > 0:
                buyer = trade.buyer.origin or trade.buyer.name
                drawn = energy.discharge(trade.traded_energy / kept_on_discharge)
                for source, drawn_kWh in drawn.items():
                    if source in pv_by_name:
                        self._credit_battery_delivery(
                            pv_by_name[source],
                            buyer,
                            drawn_kWh * kept_on_discharge,
                            flows,
                            time_slot,
                        )

        slot_days = battery.config.slot_length.total_seconds() / SECONDS_PER_DAY
        energy.self_discharge(losses.self_discharge_per_day_percent / 100 * slot_days)

    def _credit_battery_delivery(
        self,
        pv: "Area",
        buyer: str,
        energy_kWh: float,
        flows: Dict[str, _Flows],
        time_slot: DateTime,
    ) -> None:
        owner = pv.parent
        consumer = next(
            (leaf for leaf in _leaves(owner) if leaf.name == buyer and _is_consumer(leaf)), None
        )
        if consumer is None:
            return
        flows[pv.uuid].add_own_consumption(
            energy_kWh,
            self._avoided_purchase(consumer, energy_kWh, time_slot),
            _member_of(consumer, owner, set(self._record(pv).member_names)),
        )

    def _pv_result(
        self,
        record: _PVRecord,
        slot_length_seconds: float,
        parameters: RoiParameterSet,
        range_levers: RangeLevers,
    ) -> Dict:
        slots = list(record.slots.values())
        roi_inputs = record.strategy.roi_inputs
        capital_cost_per_kwp = roi_inputs.capital_cost_per_kwp or DEFAULT_CAPITAL_COST_PER_KWP
        own_kWh = sum(slot.own_consumption_kWh for slot in slots)
        sold_kWh = sum(slot.sold_kWh for slot in slots)
        community_inputs = RoiInputs(
            capacity_kwp=record.capacity_kWp or 0.0,
            capital_cost_per_kwp=capital_cost_per_kwp,
            ownership_share=1.0,
            avoided_purchase=sum(slot.avoided_purchase for slot in slots),
            sales_revenue=sum(slot.sales_revenue for slot in slots),
            window_generation_kwh=sum(slot.generation_kWh for slot in slots),
            window_days=len(slots) * slot_length_seconds / SECONDS_PER_DAY,
            annual_generation_kwh=roi_inputs.annual_generation_kWh,
        )
        members = self._member_shares(record)
        basis = self._basis(record, community_inputs, min(record.slots))
        result = self._appraise(community_inputs, parameters, range_levers, own_kWh, sold_kWh)
        result["basis"].update(basis)

        if members is not None:
            result["members"] = {}
            for member_uuid, share in members.items():
                member_own_kWh = sum(
                    slot.member_own_consumption_kWh.get(member_uuid, 0.0) for slot in slots
                )
                member_inputs = replace(
                    community_inputs,
                    ownership_share=share,
                    benefit_is_apportioned=True,
                    avoided_purchase=sum(
                        slot.member_avoided_purchase.get(member_uuid, 0.0) for slot in slots
                    ),
                    sales_revenue=share * community_inputs.sales_revenue,
                )
                member_result = self._appraise(
                    member_inputs, parameters, range_levers, member_own_kWh, share * sold_kWh
                )
                member_result["basis"].update(
                    {
                        **basis,
                        "ownership_share": share,
                        "member_uuid": member_uuid,
                        "member_name": record.member_names[member_uuid],
                    }
                )
                result["members"][member_uuid] = member_result
        return result

    @staticmethod
    def _member_shares(record: _PVRecord) -> Optional[Dict[str, float]]:
        roi_inputs = record.strategy.roi_inputs
        if not roi_inputs.ownership_member_uuids:
            return None
        shares = dict(zip(roi_inputs.ownership_member_uuids, roi_inputs.ownership_shares))
        if (
            len(roi_inputs.ownership_member_uuids) != len(roi_inputs.ownership_shares)
            or set(shares) != set(record.member_names)
            or not all(0 < share <= 1 for share in shares.values())
            or not isclose(sum(shares.values()), 1.0, abs_tol=1e-6)
        ):
            record.flags.add("member_results_withheld")
            return None
        return shares

    @staticmethod
    def _appraise(
        inputs: RoiInputs,
        parameters: RoiParameterSet,
        range_levers: RangeLevers,
        own_kWh: float,
        sold_kWh: float,
    ) -> Dict:
        result = serialize_result(calculate_roi(inputs, parameters))
        result["self_consumption_ratio"] = (
            own_kWh / inputs.window_generation_kwh if inputs.window_generation_kwh > 0 else None
        )
        if result["unavailable"] is None:
            cases = calculate_range(inputs, parameters, range_levers, own_kWh, sold_kWh)
            result["range"] = {case: serialize_result(roi) for case, roi in cases.items()}
        return result

    @staticmethod
    def _basis(record: _PVRecord, inputs: RoiInputs, window_start: DateTime) -> Dict:
        assumed = list(ASSUMED_INPUTS)
        if record.strategy.roi_inputs.capital_cost_per_kwp is not None:
            assumed.remove("capital_cost")
        return {
            "baseline_method": "analytical",
            "allocation_basis": "market_clearing",
            "price_basis": (
                "profile" if isinstance(GlobalConfig.market_maker_rate, dict) else "scalar"
            ),
            "window_start": window_start.isoformat(),
            "window_days": inputs.window_days,
            "window_is_metered": False,
            "ownership_share": inputs.ownership_share,
            "capacity_kWp": inputs.capacity_kwp,
            "capital_cost_per_kwp": inputs.capital_cost_per_kwp,
            "annual_generation_kWh": inputs.annual_generation_kwh,
            "asset_name": record.name,
            "owner_name": record.owner_name,
            "last_realised_year": None,
            "inputs_observed": list(OBSERVED_INPUTS),
            "inputs_assumed": assumed,
            "flags": sorted(record.flags),
        }
