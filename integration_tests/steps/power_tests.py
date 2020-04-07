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

import os
import glob
from behave import then
from math import isclose


@then('the export functionality of power flow result')
def test_export_of_power_flow_result(context):
    sim_data_csv = glob.glob(os.path.join(context.export_path, "*", "plot", "power_flow.html"))
    if len(sim_data_csv) != 1:
        raise FileExistsError("Not found in {path}".format(path=context.export_path))


@then('BaselinePeakEnergyStats are correctly calculated')
def test_baseline_peak_energy_stats(context):
    baseline_peak_stats = \
        context.simulation.endpoint_buffer.baseline_peak_stats.baseline_peak_percentage_result
    assert set(baseline_peak_stats.keys()) == \
        {"House 1", "House 2", "Neighborhood 1", "Neighborhood 2"}
    assert set(baseline_peak_stats["House 1"].keys()) == {"import"}
    assert set(baseline_peak_stats["Neighborhood 1"].keys()) == {"import"}
    assert set(baseline_peak_stats["House 2"].keys()) == {"export"}
    assert set(baseline_peak_stats["Neighborhood 2"].keys()) == {"export"}

    house1_branch_percentage = 0.5
    house2_branch_percentage = 1
    assert all(isclose(percentage, house1_branch_percentage)
               for percentage in baseline_peak_stats["House 1"]["import"].values())
    assert all(isclose(percentage, house1_branch_percentage)
               for percentage in baseline_peak_stats["Neighborhood 1"]["import"].values())
    assert all(isclose(percentage, house2_branch_percentage)
               for percentage in baseline_peak_stats["House 2"]["export"].values())
    assert all(isclose(percentage, house2_branch_percentage)
               for percentage in baseline_peak_stats["Neighborhood 2"]["export"].values())
