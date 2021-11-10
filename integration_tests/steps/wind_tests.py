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
from gsy_framework.read_user_profile import _readCSV
from gsy_framework.utils import convert_W_to_kWh


@then('the UserProfileWind follows the Wind profile of csv')
def check_wind_csv_profile(context):
    wind = list(filter(lambda x: x.name == "Wind Turbine", context.simulation.area.children))[0]
    from gsy_e.setup.strategy_tests.user_profile_wind_csv import user_profile_path
    profile_data = _readCSV(user_profile_path)
    for timepoint, energy in wind.strategy.state._energy_production_forecast_kWh.items():
        if timepoint in profile_data.keys():
            actual_energy = convert_W_to_kWh(profile_data[timepoint], wind.config.slot_length)
            assert energy == actual_energy
        else:
            assert energy == 0
