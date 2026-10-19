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
from math import isclose
from typing import Dict, Optional

from gsy_framework.exceptions import GSyDeviceException

SHARE_SUM_TOLERANCE = 1e-6


@dataclass(frozen=True)
class PVRoiInputs:
    """User inputs of a PV that only the return-on-investment results use.

    capacity_kWp is needed for profile PVs only, whose profile does not say how large the
    installation is. Ownership shares are keyed by member area name, because area uuids differ
    between the run with a shared PV and the baseline run without it.
    """

    capital_cost_per_kwp: Optional[float] = None
    annual_generation_kWh: Optional[float] = None
    capacity_kWp: Optional[float] = None
    ownership_shares: Dict[str, float] = field(default_factory=dict)

    def __post_init__(self):
        problems = []
        for name in ("capital_cost_per_kwp", "annual_generation_kWh", "capacity_kWp"):
            value = getattr(self, name)
            if value is not None and not value > 0:
                problems.append(f"{name} must be positive, got {value}")
        if self.ownership_shares:
            if not all(0 < share <= 1 for share in self.ownership_shares.values()):
                problems.append(
                    f"each ownership share must be in (0, 1], got {self.ownership_shares}"
                )
            if not isclose(sum(self.ownership_shares.values()), 1, abs_tol=SHARE_SUM_TOLERANCE):
                problems.append(f"ownership shares must add up to 1, got {self.ownership_shares}")
        if problems:
            raise GSyDeviceException({"misconfiguration": problems})

    @property
    def is_shared(self) -> bool:
        """True when the PV has co-owners."""
        return bool(self.ownership_shares)

    def serialize(self) -> Dict:
        """Return the constructor arguments that recreate these inputs."""
        return {
            "capital_cost_per_kwp": self.capital_cost_per_kwp,
            "annual_generation_kWh": self.annual_generation_kWh,
            "ownership_shares": dict(self.ownership_shares),
        }
