"""
Copyright 2018 Grid Singularity
This file is part of D3A.

This program is free software: you can redistribute it and/or modify it under the terms of the GNU
General Public License as published by the Free Software Foundation, either version 3 of the
License, or(at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without
even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
General Public License for more details.

You should have received a copy of the GNU General Public License along with this program. If not,
see <http://www.gnu.org/licenses/>.
"""
import random

from d3a.constants import DEFAULT_PRECISION, MAX_ENERGY_DEVIATION_PERCENT


def alter_energy(
        energy_kWh: float, max_deviation_pct: float = MAX_ENERGY_DEVIATION_PERCENT) -> float:
    """
    Compute a new energy amount that differs from the given one by (at most) a max percentage.
    """
    deviation_pct = random.uniform(-max_deviation_pct, max_deviation_pct)
    # NOTE: the deviation can be either positive or negative
    deviation_kWh = round((energy_kWh * deviation_pct) / 100.0, DEFAULT_PRECISION)
    altered_energy = energy_kWh + deviation_kWh
    # The sign of the new energy should never be flipped compared to the original
    assert (altered_energy > 0) == (energy_kWh > 0)

    return altered_energy
