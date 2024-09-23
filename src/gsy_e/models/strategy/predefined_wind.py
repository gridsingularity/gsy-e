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

from gsy_framework.constants_limits import ConstSettings
from pendulum import duration

from gsy_e.models.strategy.predefined_pv import PVUserProfileStrategy


class WindUserProfileStrategy(PVUserProfileStrategy):
    """Strategy for a wind turbine creating energy following the power_profile"""

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        power_profile=None,
        initial_selling_rate: float = ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE,
        final_selling_rate: float = ConstSettings.WindSettings.FINAL_SELLING_RATE,
        fit_to_limit: bool = True,
        update_interval=duration(minutes=ConstSettings.GeneralSettings.DEFAULT_UPDATE_INTERVAL),
        energy_rate_decrease_per_update=None,
        power_profile_uuid: str = None,
        **kwargs
    ):
        if kwargs.get("linear_pricing") is not None:
            fit_to_limit = kwargs.get("linear_pricing")

        super().__init__(
            power_profile=power_profile,
            initial_selling_rate=initial_selling_rate,
            final_selling_rate=final_selling_rate,
            fit_to_limit=fit_to_limit,
            update_interval=update_interval,
            energy_rate_decrease_per_update=energy_rate_decrease_per_update,
            power_profile_uuid=power_profile_uuid,
        )
