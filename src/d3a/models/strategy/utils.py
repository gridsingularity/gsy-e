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
import numpy as np

from d3a.constants import DEFAULT_PRECISION, RELATIVE_STD_FROM_FORECAST_ENERGY


def alter_energy(
        energy_kWh: float, relative_std: float = RELATIVE_STD_FROM_FORECAST_ENERGY,
        random_generator: np.random.Generator = np.random.RandomState()) -> float:
    """
    Compute a new energy amount, modelling its value on a normal distribution based on the old one.

    Args:
        energy_kWh: the amount of energy to be altered.
        relative_sdt: the percentage of original energy to be used to set the standard deviation
            of the normal distribution.
        random_generator: a numpy random generator instance.
    """
    std = (relative_std * energy_kWh) / 100
    # Create a random number generator to avoid using np.random (that would alter the global seed)
    altered_energy_kWh = random_generator.normal(loc=energy_kWh, scale=std)
    # If the sign of the new energy flipped compared to the original, clip it to 0
    if (altered_energy_kWh > 0) != (energy_kWh > 0):
        return 0

    return round(altered_energy_kWh, DEFAULT_PRECISION)
