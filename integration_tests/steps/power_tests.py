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


@then('the export functionality of power flow result')
def test_export_of_power_flow_result(context):
    sim_data_csv = glob.glob(os.path.join(context.export_path, "*", "plot", "power_flow.html"))
    if len(sim_data_csv) != 1:
        raise FileExistsError("Not found in {path}".format(path=context.export_path))


@then('BaselinePeakEnergyStats are correctly calculated')
def test_baseline_peak_energy_stats(context):
    area_throughput_stats = \
        context.simulation.endpoint_buffer.area_throughput_stats.results
    stats_area_name = []
    for area_name, market_value in area_throughput_stats.items():
        stats_area_name.append(area_name)
        if area_name in ['Grid', 'House 1 2']:
            assert all(stats['import']['peak_energy_kWh'] == 0
                       for market_time, stats in market_value.items())
            assert all(stats['export']['peak_energy_kWh'] == 0
                       for market_time, stats in market_value.items())
            assert all(stats['net_energy_flow']['peak_energy_kWh'] == 0
                       for market_time, stats in market_value.items())
        elif area_name in ['Neighborhood 1', 'House 1']:
            assert all(stats['import']['peak_energy_kWh'] == 0.2
                       for market_time, stats in market_value.items())
            assert all(stats['import']['baseline_peak_energy_kWh'] == 0.4
                       for market_time, stats in market_value.items())
            assert all(stats['import']['peak_percentage'] == 50.0
                       for market_time, stats in market_value.items())
            assert all(stats['export']['peak_energy_kWh'] == 0
                       for market_time, stats in market_value.items())
            assert all(stats['net_energy_flow']['peak_energy_kWh'] == 0.2
                       for market_time, stats in market_value.items())
        elif area_name in ['Neighborhood 2', 'House 2']:
            assert all(stats['import']['peak_energy_kWh'] == 0.
                       for market_time, stats in market_value.items())
            assert all(stats['export']['peak_energy_kWh'] == 0.3
                       for market_time, stats in market_value.items())
            assert all(stats['export']['baseline_peak_energy_kWh'] == 0.3
                       for market_time, stats in market_value.items())
            assert all(stats['export']['peak_percentage'] == 100.0
                       for market_time, stats in market_value.items())
            assert all(stats['net_energy_flow']['peak_energy_kWh'] == -0.3
                       for market_time, stats in market_value.items())
        else:
            assert False

    assert stats_area_name == ['Grid', 'Neighborhood 1', 'House 1', 'House 1 2',
                               'Neighborhood 2', 'House 2']
