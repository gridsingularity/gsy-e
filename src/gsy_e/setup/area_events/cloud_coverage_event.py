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
from gsy_e.models.area import Market, Asset
from gsy_e.models.area.event_types import ConfigEvents
from gsy_e.models.strategy.load_hours import LoadHoursStrategy
from gsy_e.models.strategy.predefined_pv import PVPredefinedStrategy


def get_setup(config):
    area = Market(
        "Grid",
        [
            Market(
                "House 1",
                event_list=[ConfigEvents(12, {"cloud_coverage": 1})],
                children=[
                    Asset("H1 PV", strategy=PVPredefinedStrategy(capacity_kW=0.25),
                          ),
                ]
            ),
            Market(
                "House 2",
                event_list=[ConfigEvents(12, {"cloud_coverage": 2})],
                children=[
                    Asset("H2 PV", strategy=PVPredefinedStrategy(capacity_kW=0.25),
                          ),

                ]
            ),
            Asset("Grid Load", strategy=LoadHoursStrategy(avg_power_W=100000,
                                                          hrs_of_day=list(
                                                              range(0, 24)),
                                                          final_buying_rate=35)
                  ),
        ],
        config=config
    )
    return area
