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

from dataclasses import dataclass
from typing import Dict, Optional, Sequence, Tuple


@dataclass(frozen=True)
class PVRoiInputs:
    """User inputs of a PV that only the return-on-investment results use.

    capacity_kWp is needed for profile PVs only, whose profile does not say how large the
    installation is. Ownership shares are given per member area uuid and must sum to 1 for
    member results to be produced.
    """

    capital_cost_per_kwp: Optional[float] = None
    annual_generation_kWh: Optional[float] = None
    capacity_kWp: Optional[float] = None
    ownership_member_uuids: Tuple[str, ...] = ()
    ownership_shares: Tuple[float, ...] = ()

    @classmethod
    def from_arguments(
        cls,
        capital_cost_per_kwp: Optional[float] = None,
        annual_generation_kWh: Optional[float] = None,
        capacity_kWp: Optional[float] = None,
        ownership_member_uuids: Optional[Sequence[str]] = None,
        ownership_shares: Optional[Sequence[float]] = None,
    ) -> "PVRoiInputs":
        """Build the inputs from strategy constructor arguments, where lists may be None."""
        return cls(
            capital_cost_per_kwp=capital_cost_per_kwp,
            annual_generation_kWh=annual_generation_kWh,
            capacity_kWp=capacity_kWp,
            ownership_member_uuids=tuple(ownership_member_uuids or ()),
            ownership_shares=tuple(ownership_shares or ()),
        )

    def serialize(self) -> Dict:
        """Return the constructor arguments that recreate these inputs."""
        return {
            "capital_cost_per_kwp": self.capital_cost_per_kwp,
            "annual_generation_kWh": self.annual_generation_kWh,
            "ownership_member_uuids": list(self.ownership_member_uuids),
            "ownership_shares": list(self.ownership_shares),
        }
