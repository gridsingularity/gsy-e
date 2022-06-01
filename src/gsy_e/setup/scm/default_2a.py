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

from gsy_framework.constants_limits import ConstSettings, SpotMarketTypeEnum
from gsy_e.models.area import CoefficientArea
from gsy_e.models.strategy.scm.load import SCMLoadHoursStrategy
from gsy_e.models.strategy.scm.pv import SCMPVStrategy
from gsy_e.models.strategy.scm.storage import SCMStorageStrategy
from gsy_e.models.strategy.scm.smart_meter import SCMSmartMeterStrategy


def get_setup(config):
    ConstSettings.MASettings.MARKET_TYPE = SpotMarketTypeEnum.COEFFICIENTS.value
    area = CoefficientArea(
        "Grid",
        [
            CoefficientArea(
                "House 1",
                [
                    CoefficientArea("H1 General Load",
                                    strategy=SCMLoadHoursStrategy(avg_power_W=200,
                                                                  hrs_per_day=6,
                                                                  hrs_of_day=list(
                                                                    range(12, 18)))),
                    CoefficientArea("H1 PV", strategy=SCMPVStrategy(capacity_kW=0.9)),
                    CoefficientArea("H1 Storage1", strategy=SCMStorageStrategy(initial_soc=50)),
                    CoefficientArea("H1 Storage2", strategy=SCMStorageStrategy(initial_soc=50)),
                ],
                grid_fee_percentage=0, grid_fee_constant=0,
            ),
            CoefficientArea(
                "House 2",
                [
                    CoefficientArea("H2 General Load",
                                    strategy=SCMLoadHoursStrategy(avg_power_W=200,
                                                                  hrs_per_day=4,
                                                                  hrs_of_day=list(
                                                                      range(12, 16)))),
                    CoefficientArea("H2 PV", strategy=SCMPVStrategy(capacity_kW=0.9)),
                    CoefficientArea("H2 Smart Meter",
                                    strategy=SCMSmartMeterStrategy(smart_meter_profile={0: 100})),
                ],
                grid_fee_percentage=0, grid_fee_constant=0,

            ),
            CoefficientArea("Cell Tower",
                            strategy=SCMLoadHoursStrategy(avg_power_W=100,
                                                          hrs_per_day=24,
                                                          hrs_of_day=list(range(0, 24)))),
        ],
        config=config
    )
    return area
