from logging import getLogger
from typing import Dict

import pendulum

logger = getLogger(__name__)


class ProfileScaler:
    """Class to scale existing profiles based on a new peak."""

    def __init__(self, profile: Dict):
        self._original_profile: Dict[pendulum.DateTime, float] = profile

    def scale_by_peak(self, peak_kWh: float) -> Dict[pendulum.DateTime, float]:
        """Return a profile obtained by scaling the original one using a new peak capacity."""
        scaling_factor = self._compute_scaling_factor(peak_kWh)
        return self._scale_by_factor(scaling_factor)

    @property
    def _original_peak_kWh(self) -> float:
        return max(self._original_profile.values())

    def _compute_scaling_factor(self, peak_kWh: float) -> float:
        """Compute the ratio to be used to scale the original profile based on the new peak."""
        return peak_kWh / self._original_peak_kWh

    def _scale_by_factor(self, scaling_factor: float):
        """Scale the original profile using the scaling factor."""
        return {
            date: energy * scaling_factor
            for date, energy in self._original_profile.items()
        }
