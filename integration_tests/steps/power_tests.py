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
    area_throughput_stats = \
        context.simulation.endpoint_buffer.area_throughput_stats.results
    stats_area_name = []
    for area_name, market_value in area_throughput_stats.items():
        stats_area_name.append(area_name)
        if area_name in ['Grid', 'House 1 2']:
            assert all(stats['import']['peak_energy_trade_kWh'] == 0
                       for market_time, stats in market_value.items())
            assert all(stats['import']['peak_energy_net_kWh'] == 0
                       for market_time, stats in market_value.items())
            assert all(stats['export']['peak_energy_trade_kWh'] == 0
                       for market_time, stats in market_value.items())
            assert all(stats['export']['peak_energy_net_kWh'] == 0
                       for market_time, stats in market_value.items())
            assert all(stats['net_energy_flow']['peak_energy_kWh'] == 0
                       for market_time, stats in market_value.items())
        elif area_name in ['Neighborhood 1', 'House 1']:
            assert all(stats['import']['peak_energy_trade_kWh'] == 0.2
                       for market_time, stats in market_value.items())
            assert all(stats['import']['peak_energy_net_kWh'] == 0.2
                       for market_time, stats in market_value.items())
            assert all(stats['import']['baseline_peak_energy_kWh'] == 0.4
                       for market_time, stats in market_value.items())
            assert all(stats['import']['peak_percentage'] == 50.0
                       for market_time, stats in market_value.items())
            assert all(stats['export']['peak_energy_trade_kWh'] == 0
                       for market_time, stats in market_value.items())
            assert all(stats['export']['peak_energy_net_kWh'] == 0
                       for market_time, stats in market_value.items())
            assert all(stats['net_energy_flow']['peak_energy_kWh'] == 0.2
                       for market_time, stats in market_value.items())
        elif area_name in ['Neighborhood 2', 'House 2']:
            assert all(stats['import']['peak_energy_trade_kWh'] == 0.
                       for market_time, stats in market_value.items())
            assert all(stats['import']['peak_energy_net_kWh'] == 0.
                       for market_time, stats in market_value.items())
            assert all(stats['export']['peak_energy_trade_kWh'] == 0.3
                       for market_time, stats in market_value.items())
            assert all(stats['export']['peak_energy_net_kWh'] == 0.3
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


@then('NetEnergyFlowStats are correctly calculated')
def test_net_energy_flow_stats(context):
    from integration_tests.steps.integration_tests import get_simulation_raw_results
    get_simulation_raw_results(context)
    from d3a.d3a_core.sim_results.area_throughput_stats import AreaThroughputStats
    area_throughput = AreaThroughputStats()
    for time_slot, core_stats in context.raw_sim_data.items():

        area_throughput.update(context.area_tree_summary_data, core_stats, time_slot)
        house_result = area_throughput.results_redis[context.name_uuid_map['House 1']][time_slot]
        assert house_result['import']['peak_energy_trade_kWh'] == 1.0
        assert house_result['import']['peak_energy_net_kWh'] == 0.5
        exp_percentage = (house_result['import']['peak_energy_net_kWh'] /
                          house_result['import']['baseline_peak_energy_kWh']) * 100
        assert house_result['import']['peak_percentage'] == exp_percentage
        assert house_result['import']['baseline_peak_energy_kWh'] == 1
        assert house_result['import']['capacity_kWh'] == 1
        assert house_result['export']['peak_energy_trade_kWh'] == 0.5
        assert isclose(house_result['export']['peak_energy_net_kWh'], 0.0, rel_tol=1e-1)
        exp_percentage = (house_result['export']['peak_energy_net_kWh'] /
                          house_result['export']['baseline_peak_energy_kWh']) * 100
        assert isclose(house_result['export']['peak_percentage'], exp_percentage, abs_tol=1e-10)
        assert isclose(house_result['net_energy_flow']['peak_energy_kWh'], 0.5, rel_tol=1e-1)
