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

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, Iterator, List, Optional, Set

from gsy_framework.constants_limits import ConstSettings, GlobalConfig
from gsy_framework.sim_results.roi.appraisal import calculate_roi
from gsy_framework.sim_results.roi.data_classes import RoiInputs, RoiParameterSet
from gsy_framework.sim_results.roi.parameters import (
    DEFAULT_CAPITAL_COST_PER_KWP,
    DEFAULT_PARAMETER_SET,
)
from gsy_framework.sim_results.roi.serialization import serialize_result
from pendulum import DateTime

from gsy_e.gsy_e_core.util import get_market_maker_rate_from_time_slot
from gsy_e.models.base import AssetType
from gsy_e.models.strategy.pv import PVStrategy
from gsy_e.models.strategy.smart_meter import SmartMeterStrategy
from gsy_e.models.strategy.storage import StorageStrategy

if TYPE_CHECKING:
    from gsy_e.models.area import Area
    from gsy_e.models.market import MarketBase

CENTS_PER_CURRENCY_UNIT = 100
CONSTANT_GRID_FEE_TYPE = 1
SECONDS_PER_DAY = 86400

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


@dataclass
class _SlotTotals:
    own_consumption_kWh: float = 0.0
    avoided_purchase: float = 0.0
    sales_revenue: float = 0.0
    generation_kWh: float = 0.0


@dataclass
class _PVRecord:
    name: str
    owner_name: str
    capacity_kWp: Optional[float]
    capital_cost_per_kwp: Optional[float]
    slots: Dict[DateTime, _SlotTotals] = field(default_factory=dict)
    flags: Set[str] = field(default_factory=set)


def _leaves(area: "Area") -> Iterator["Area"]:
    for child in area.children:
        if child.children:
            yield from _leaves(child)
        elif child.strategy is not None:
            yield child


def _is_own_consumer(area: "Area") -> bool:
    return (
        isinstance(area.strategy, SmartMeterStrategy)
        or area.strategy.asset_type is AssetType.CONSUMER
    )


def _capacity_kWp(strategy: PVStrategy) -> Optional[float]:
    profile_capacity = getattr(strategy, "roi_capacity_kW", None)
    if profile_capacity is not None:
        return profile_capacity
    return getattr(strategy._energy_params, "capacity_kW", None)  # pylint: disable=W0212


class RoiLedger:
    """Collect, per PV and market slot, the totals of the trade-based RoI baseline.

    The owner of a PV is the area that contains it. Energy the PV sells to a consumer inside that
    area is valued at the supplier rate plus the grid fees the consumer would otherwise have paid
    (D7.3 equation 4a). Energy it sells outside the area is revenue (equation 4b). Energy sold to
    a battery in the area is neither, and the result is flagged.
    """

    def __init__(self):
        self._records: Dict[str, _PVRecord] = {}

    def update(self, root_area: "Area") -> None:
        """Record the current spot market slot of every PV, replacing an earlier record of it."""
        for leaf in _leaves(root_area):
            if not isinstance(leaf.strategy, PVStrategy):
                continue
            market = leaf.parent.spot_market
            if market is None:
                continue
            record = self._records.setdefault(
                leaf.uuid,
                _PVRecord(
                    name=leaf.name,
                    owner_name=leaf.parent.name,
                    capacity_kWp=_capacity_kWp(leaf.strategy),
                    capital_cost_per_kwp=leaf.strategy.capital_cost_per_kwp,
                ),
            )
            record.slots[market.time_slot] = self._slot_totals(leaf, market, record.flags)

    def results(self, slot_length_seconds: float, parameters: RoiParameterSet = None) -> Dict:
        """Return the serialised RoI result of every PV, keyed by its uuid."""
        parameters = parameters or DEFAULT_PARAMETER_SET
        return {
            uuid: self._result(record, slot_length_seconds, parameters)
            for uuid, record in self._records.items()
            if record.slots
        }

    @staticmethod
    def _slot_totals(pv: "Area", market: "MarketBase", flags: Set[str]) -> _SlotTotals:
        owner = pv.parent
        consumers = {leaf.name: leaf for leaf in _leaves(owner) if _is_own_consumer(leaf)}
        batteries = {
            leaf.name for leaf in _leaves(owner) if isinstance(leaf.strategy, StorageStrategy)
        }
        pv_count = sum(isinstance(leaf.strategy, PVStrategy) for leaf in _leaves(owner))
        if batteries:
            flags.add("storage_attribution_excluded")
        if pv_count > 1:
            flags.add("not_separable")
        grid_fee_type = (
            owner.config.grid_fee_type if owner.config else ConstSettings.MASettings.GRID_FEE_TYPE
        )
        if grid_fee_type != CONSTANT_GRID_FEE_TYPE:
            flags.add("percentage_grid_fees_excluded")

        supplier_rate = get_market_maker_rate_from_time_slot(market.time_slot) or 0
        totals = _SlotTotals(
            generation_kWh=pv.strategy.state.get_energy_production_forecast_kWh(
                market.time_slot, 0.0
            )
        )
        for trade in market.trades:
            if trade.seller.name != pv.name:
                continue
            buyer = trade.buyer.origin or trade.buyer.name
            if buyer in consumers:
                path_fee = consumers[buyer].parent.get_path_to_root_fees()
                totals.own_consumption_kWh += trade.traded_energy
                totals.avoided_purchase += (
                    trade.traded_energy * (supplier_rate + path_fee) / CENTS_PER_CURRENCY_UNIT
                )
            elif buyer not in batteries:
                totals.sales_revenue += (
                    trade.trade_price - trade.fee_price
                ) / CENTS_PER_CURRENCY_UNIT
        return totals

    @staticmethod
    def _result(
        record: _PVRecord, slot_length_seconds: float, parameters: RoiParameterSet
    ) -> Dict:
        slots = record.slots.values()
        own_consumption_kWh = sum(slot.own_consumption_kWh for slot in slots)
        generation_kWh = sum(slot.generation_kWh for slot in slots)
        assumed: List[str] = list(ASSUMED_INPUTS)
        capital_cost_per_kwp = record.capital_cost_per_kwp
        if capital_cost_per_kwp is None:
            capital_cost_per_kwp = DEFAULT_CAPITAL_COST_PER_KWP
        else:
            assumed.remove("capital_cost")

        inputs = RoiInputs(
            capacity_kwp=record.capacity_kWp or 0.0,
            capital_cost_per_kwp=capital_cost_per_kwp,
            ownership_share=1.0,
            avoided_purchase=sum(slot.avoided_purchase for slot in slots),
            sales_revenue=sum(slot.sales_revenue for slot in slots),
            window_generation_kwh=generation_kWh,
            window_days=len(record.slots) * slot_length_seconds / SECONDS_PER_DAY,
        )
        result = serialize_result(calculate_roi(inputs, parameters))
        result["self_consumption_ratio"] = (
            own_consumption_kWh / generation_kWh if generation_kWh > 0 else None
        )
        result["basis"].update(
            {
                "baseline_method": "analytical",
                "allocation_basis": "market_clearing",
                "price_basis": (
                    "profile" if isinstance(GlobalConfig.market_maker_rate, dict) else "scalar"
                ),
                "window_start": min(record.slots).isoformat(),
                "window_days": inputs.window_days,
                "window_is_metered": False,
                "ownership_share": inputs.ownership_share,
                "capacity_kWp": inputs.capacity_kwp,
                "capital_cost_per_kwp": capital_cost_per_kwp,
                "asset_name": record.name,
                "owner_name": record.owner_name,
                "last_realised_year": None,
                "inputs_observed": [
                    "capacity",
                    "ledger_flows",
                    "generation",
                    "self_consumption_ratio",
                ],
                "inputs_assumed": assumed,
                "flags": sorted(record.flags),
            }
        )
        return result
