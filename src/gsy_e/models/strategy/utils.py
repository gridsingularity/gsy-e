"""
Copyright 2018 Grid Singularity
This file is part of Grid Singularity Exchange

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

from gsy_framework.constants_limits import ConstSettings
from gsy_framework.enums import SpotMarketTypeEnum
from gsy_framework.utils import limit_float_precision


def compute_altered_energy(
    energy_kWh: float,
    relative_std: float = ConstSettings.SettlementMarketSettings.RELATIVE_STD_FROM_FORECAST_FLOAT,
    random_generator: random.Random = random.Random(12)
) -> float:
    """
    Compute a new energy amount, modelling its value on a normal distribution of the old amount.

    Args:
        energy_kWh: the amount of energy to be altered.
        relative_std: the percentage of original energy to be used to set the standard deviation
            of the normal distribution.
        random_generator: a pseudo-random number generator instance. This is used to return
            reproducible results while not altering the global random seed.
    """
    std = (relative_std * energy_kWh) / 100
    altered_energy_kWh = random_generator.gauss(mu=energy_kWh, sigma=std)
    # If the sign of the new energy flipped compared to the original, clip it to 0
    if (altered_energy_kWh > 0) != (energy_kWh > 0):
        return 0

    return limit_float_precision(altered_energy_kWh)


def is_scm_simulation():
    """Return true if simulation is an SCM one, false otherwise."""
    return ConstSettings.MASettings.MARKET_TYPE == SpotMarketTypeEnum.COEFFICIENTS.value
