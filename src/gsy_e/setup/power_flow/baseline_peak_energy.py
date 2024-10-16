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
from gsy_e.models.area import Area
from gsy_e.models.strategy.load_hours import LoadHoursStrategy
from gsy_e.models.strategy.finite_power_plant import FinitePowerPlant
from gsy_e.models.area.throughput_parameters import ThroughputParameters


def get_setup(config):
    area = Area(
        "Grid",
        [Area("Neighborhood 1",
              [
                Area(
                    "House 1",
                    [
                        Area("H1 General Load", strategy=LoadHoursStrategy(avg_power_W=200,
                                                                           hrs_of_day=list(
                                                                               range(0, 24)),
                                                                           final_buying_rate=35)
                             ),
                    ],
                    grid_fee_percentage=0, grid_fee_constant=0,
                    throughput=ThroughputParameters(baseline_peak_energy_import_kWh=0.4)
                ),
                Area(
                      "House 1 2", [], throughput=ThroughputParameters(import_capacity_kVA=2.0,
                                                                       export_capacity_kVA=2.0)
                  ),
              ], throughput=ThroughputParameters(baseline_peak_energy_import_kWh=0.4,
                                                 import_capacity_kVA=2.0)
              ),
            Area("Neighborhood 2",
                 [
                    Area(
                        "House 2",
                        [
                            Area("H2 Diesel Generator",
                                 strategy=FinitePowerPlant(max_available_power_kW=300,
                                                           energy_rate=20)
                                 ),
                        ],
                        grid_fee_percentage=0, grid_fee_constant=0,
                        throughput=ThroughputParameters(baseline_peak_energy_export_kWh=0.3)

                    ),
                    ], throughput=ThroughputParameters(baseline_peak_energy_export_kWh=0.3,
                                                       export_capacity_kVA=2.0)
                 ),
            Area("Global Load", strategy=LoadHoursStrategy(avg_power_W=100,
                                                           hrs_of_day=list(range(0, 24)),
                                                           final_buying_rate=35)
                 ),
         ],
        config=config
    )
    return area
