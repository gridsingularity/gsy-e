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
from behave import then
from d3a.models.read_user_profile import _readCSV
from d3a.constants import PENDULUM_TIME_FORMAT


@then('the UserProfileWind follows the Wind profile of csv')
def check_wind_csv_profile(context):
    wind = list(filter(lambda x: x.name == "Wind Turbine", context.simulation.area.children))[0]
    from d3a.setup.strategy_tests.user_profile_wind_csv import user_profile_path
    profile_data = _readCSV(user_profile_path)
    for timepoint, energy in wind.strategy.energy_production_forecast_kWh.items():

        time = str(timepoint.format(PENDULUM_TIME_FORMAT))
        accumulated_energy = 0
        for time_str in profile_data.keys():
            if int(time_str[:2]) == int(timepoint.hour):
                accumulated_energy += (profile_data[time_str] * 0.25)
        if time in profile_data.keys():
            actual_energy = accumulated_energy / 1000.0
            assert energy == actual_energy
        else:
            assert energy == 0
