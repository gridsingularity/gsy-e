"""
Copyright 2018 Grid Singularity
This file is part of D3A.

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
from d3a_interface.constants_limits import ConstSettings
from d3a.models.strategy.predefined_pv import PVUserProfileStrategy
from pendulum import duration

"""
Creates a WindStrategy that uses a profile as input for its power values.
"""


class WindUserProfileStrategy(PVUserProfileStrategy):
    parameters = ('power_profile', 'panel_count')

    def __init__(self, power_profile,
                 initial_selling_rate:
                 float = ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE,
                 final_selling_rate: float=ConstSettings.WindSettings.FINAL_SELLING_RATE,
                 fit_to_limit: bool = True,
                 update_interval=duration(minutes=ConstSettings.GeneralSettings.UPDATE_RATE),
                 energy_rate_decrease_per_update:
                 float = ConstSettings.GeneralSettings.ENERGY_RATE_DECREASE_PER_UPDATE,
                 max_wind_turbine_power_W: float =
                 ConstSettings.WindSettings.MAX_WIND_TURBINE_OUTPUT_W
                 ):
        super().__init__(power_profile=power_profile, initial_selling_rate=initial_selling_rate,
                         final_selling_rate=final_selling_rate,
                         fit_to_limit=fit_to_limit, update_interval=update_interval,
                         energy_rate_decrease_per_update=energy_rate_decrease_per_update,
                         max_panel_power_W=max_wind_turbine_power_W
                         )
