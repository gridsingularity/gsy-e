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
import os

from gsy_e.constants import DEFAULT_SCM_COMMUNITY_NAME
from gsy_e.gsy_e_core.util import gsye_root_path
from gsy_e.models.area import CoefficientArea
from gsy_e.models.strategy.scm.external.load import ForecastSCMLoadStrategy
from gsy_e.models.strategy.scm.external.pv import ForecastSCMPVStrategy
from gsy_e.models.strategy.scm.load import SCMLoadHoursStrategy
from gsy_e.models.strategy.scm.pv import SCMPVUserProfile
from gsy_e.models.strategy.scm.smart_meter import SCMSmartMeterStrategy
from gsy_e.models.strategy.scm.storage import SCMStorageStrategy

pv_profile = os.path.join(gsye_root_path, "resources", "Solar_Curve_W_sunny.csv")
load_profile = os.path.join(gsye_root_path, "resources", "LOAD_DATA_1.csv")


def get_setup(config):
    area = CoefficientArea(
        DEFAULT_SCM_COMMUNITY_NAME,
        [
            CoefficientArea(
                "House 1",
                [
                    CoefficientArea("H1 General Load",
                                    strategy=SCMLoadHoursStrategy(avg_power_W=200,
                                                                  hrs_of_day=list(
                                                                      range(12, 18)))),
                    CoefficientArea("H1 PV", strategy=SCMPVUserProfile(power_profile=pv_profile)),
                    CoefficientArea("H1 Storage1", strategy=SCMStorageStrategy(initial_soc=50)),
                    CoefficientArea("H1 Storage2", strategy=SCMStorageStrategy(initial_soc=50)),
                ],
                grid_fee_percentage=0, grid_fee_constant=0, coefficient_percentage=0.6
            ),
            CoefficientArea(
                "House 2",
                [
                    CoefficientArea("forecast-measurement-load",
                                    strategy=ForecastSCMLoadStrategy(
                                        daily_load_profile=load_profile)),
                    CoefficientArea("forecast-measurement-pv",
                                    strategy=ForecastSCMPVStrategy()),
                    CoefficientArea("H2 Smart Meter",
                                    strategy=SCMSmartMeterStrategy(smart_meter_profile={0: 100})),
                ],
                grid_fee_percentage=0, grid_fee_constant=0, coefficient_percentage=0.4

            ),
        ],
        config=config
    )
    return area
