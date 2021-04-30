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

from d3a_interface.utils import get_area_name_uuid_mapping


@then('{kpi} of {expected_kpis} are correctly reported')
def test_export_of_kpi_result(context, kpi, expected_kpis):
    area_tree_summary = glob.glob(os.path.join(context.export_path, "*", "area_tree_summary.json"))
    with open(area_tree_summary[0], "r") as sf:
        context.area_tree_summary_data = json.load(sf)
    name_uuid_map = get_area_name_uuid_mapping(context.area_tree_summary_data)

    sim_data_csv = glob.glob(os.path.join(context.export_path, "*",
                                          "aggregated_results", "kpi.json"))
    with open(sim_data_csv[0], "r") as sf:
        kpi_data = json.load(sf)
    expected_kpis = ast.literal_eval(expected_kpis)
    for area, value in expected_kpis.items():
        area_uuid = name_uuid_map[area]
        if kpi == "self_sufficiency":
            assert isclose(kpi_data[area_uuid]['self_sufficiency'], float(value), abs_tol=1e-03)

            assert isclose(
                kpi_data[area_uuid]['self_sufficiency'],
                min(kpi_data[area_uuid]['total_self_consumption_wh'] /
                    kpi_data[area_uuid]['total_energy_demanded_wh'], 1.0), abs_tol=1e-03)

        elif kpi == "self_consumption":
            if value is None:
                assert kpi_data[area_uuid]['self_consumption'] is None
            else:
                assert isclose(kpi_data[area_uuid]['self_consumption'],
                               float(value), rel_tol=1e-02)

                assert isclose(
                    kpi_data[area_uuid]['self_consumption'],
                    min(kpi_data[area_uuid]['total_self_consumption_wh'] /
                        kpi_data[area_uuid]['total_energy_produced_wh'], 1.0), abs_tol=1e-03)
        elif kpi == "total_energy_demanded_wh":
            assert isclose(kpi_data[area_uuid]['total_energy_demanded_wh'],
                           float(value), abs_tol=1e-03)
        elif kpi == "total_energy_produced_wh":
            assert isclose(kpi_data[area_uuid]['total_energy_produced_wh'],
                           float(value), abs_tol=1e-03)
        elif kpi == "total_self_consumption_wh":
            assert isclose(kpi_data[area_uuid]['total_self_consumption_wh'],
                           float(value), abs_tol=1e-03)
