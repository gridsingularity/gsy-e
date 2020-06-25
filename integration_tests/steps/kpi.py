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
import json
import glob
import ast
from behave import then
from math import isclose
from d3a.constants import DEVICE_PENALTY_RATE


@then('{kpi} of {expected_kpis} are correctly reported')
def test_export_of_kpi_result(context, kpi, expected_kpis):
    sim_data_csv = glob.glob(os.path.join(context.export_path, "*",
                                          "aggregated_results", "kpi.json"))
    with open(sim_data_csv[0], "r") as sf:
        kpi_data = json.load(sf)
    expected_kpis = ast.literal_eval(expected_kpis)
    for area, value in expected_kpis.items():
        if kpi == "self_sufficiency":
            assert isclose(kpi_data[area]['self_sufficiency'], float(value), abs_tol=1e-03)

            assert isclose(kpi_data[area]['self_sufficiency'],
                           min(kpi_data[area]['total_self_consumption_wh'] /
                               kpi_data[area]['total_energy_demanded_wh'], 1.0), abs_tol=1e-03)

        elif kpi == "self_consumption":
            if value is None:
                assert kpi_data[area]['self_consumption'] is None
            else:
                assert isclose(kpi_data[area]['self_consumption'],
                               float(value), rel_tol=1e-02)

                assert isclose(kpi_data[area]['self_consumption'],
                               min(kpi_data[area]['total_self_consumption_wh'] /
                                   kpi_data[area]['total_energy_produced_wh'], 1.0), abs_tol=1e-03)
        elif kpi == "total_energy_demanded_wh":
            assert isclose(kpi_data[area]['total_energy_demanded_wh'], float(value), abs_tol=1e-03)
        elif kpi == "total_energy_produced_wh":
            assert isclose(kpi_data[area]['total_energy_produced_wh'], float(value), abs_tol=1e-03)
        elif kpi == "total_self_consumption_wh":
            assert isclose(kpi_data[area]['total_self_consumption_wh'],
                           float(value), abs_tol=1e-03)


@then("device '{device_name}' reports penalties of {penalty_energy} kWh")
def device_reports_penalties(context, device_name, penalty_energy):
    house1 = list(filter(lambda x: x.name == "House 1", context.simulation.area.children))[0]
    device = list(filter(lambda x: device_name in x.name, house1.children))[0]
    bills = context.simulation.endpoint_buffer.market_bills.bills_redis_results
    assert isclose(bills[str(device.uuid)]["penalty_energy"], float(penalty_energy))


@then("device '{device_name}' does not report penalties")
def device_does_not_report_penalties(context, device_name):
    house2 = list(filter(lambda x: x.name == "House 2", context.simulation.area.children))[0]
    device = list(filter(lambda x: device_name in x.name, house2.children))[0]
    bills = context.simulation.endpoint_buffer.market_bills.bills_redis_results
    assert isclose(bills[str(device.uuid)]["penalty_energy"], 0.0)
    assert isclose(bills[str(device.uuid)]["penalty_cost"], 0.0)


@then("the penalties of the '{load_name}' is the sum of the residual energy requirement")
def residual_energy_req_equals_to_penalties(context, load_name):
    house1 = list(filter(lambda x: x.name == "House 1", context.simulation.area.children))[0]
    load = list(filter(lambda x: load_name in x.name, house1.children))[0]
    bills = context.simulation.endpoint_buffer.market_bills.bills_redis_results
    penalty_energy = sum(v / 1000.0 for _, v in load.strategy.energy_requirement_Wh.items())
    assert isclose(bills[str(load.uuid)]["penalty_energy"], penalty_energy, rel_tol=0.0003)


@then("the penalties of the '{pv_name}' is the sum of the residual available energy")
def available_energy_equals_to_penalties(context, pv_name):
    house1 = list(filter(lambda x: x.name == "House 1", context.simulation.area.children))[0]
    pv = list(filter(lambda x: pv_name in x.name, house1.children))[0]
    bills = context.simulation.endpoint_buffer.market_bills.bills_redis_results
    penalty_energy = sum(v for _, v in pv.strategy.state.available_energy_kWh.items())
    assert isclose(bills[str(pv.uuid)]["penalty_energy"], penalty_energy, rel_tol=0.0003)


@then("the penalty cost of the '{device_name}' is respecting the penalty rate")
def penalty_rate_respected(context, device_name):
    house1 = list(filter(lambda x: x.name == "House 1", context.simulation.area.children))[0]
    device = list(filter(lambda x: device_name in x.name, house1.children))[0]
    bills = context.simulation.endpoint_buffer.market_bills.bills_redis_results
    assert isclose(bills[str(device.uuid)]["penalty_cost"],
                   bills[str(device.uuid)]["penalty_energy"] * DEVICE_PENALTY_RATE / 100.0,
                   rel_tol=0.0003 * DEVICE_PENALTY_RATE)
    assert isclose(bills[str(house1.uuid)]["Accumulated Trades"]["penalty_cost"],
                   bills[str(device.uuid)]["penalty_cost"])
    assert isclose(bills[str(house1.uuid)]["Accumulated Trades"]["penalty_energy"],
                   bills[str(device.uuid)]["penalty_energy"])


@then('totals_with_penalties are correctly populated for all areas in the bills')
def totals_with_penalties_bills_test(context):
    bills = context.simulation.endpoint_buffer.market_bills.bills_results
    expected_grid_totals = sum(bills[house]["totals_with_penalties"]["costs"]
                               for house in ["House 1", "House 2"])
    assert isclose(bills["Grid"]["totals_with_penalties"]["costs"], expected_grid_totals)

    for house_name in ["House 1", "House 2"]:
        house_obj = \
            list(filter(lambda x: x.name == house_name, context.simulation.area.children))[0]
        expected_house_totals = \
            sum(bills[child.name]["totals_with_penalties"] for child in house_obj.children)
        assert isclose(bills[house_name]["totals_with_penalties"]["costs"], expected_house_totals)

        for child in house_obj.children:
            assert isclose(bills[child.name]["totals_with_penalties"],
                           bills[child.name]["total_cost"] + bills[child.name]["penalty_cost"])
