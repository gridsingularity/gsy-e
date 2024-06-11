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

from gsy_framework.constants_limits import ConstSettings, SpotMarketTypeEnum
from pendulum import today

from gsy_e.constants import DEFAULT_SCM_COMMUNITY_NAME
from gsy_e.gsy_e_core.util import gsye_root_path
from gsy_e.models.area import CoefficientArea
from gsy_e.models.strategy.scm.heat_pump import ScmHeatPumpStrategy
from gsy_e.models.strategy.scm.load import SCMLoadHoursStrategy
from gsy_e.models.strategy.scm.pv import SCMPVUserProfile
from gsy_e.models.strategy.scm.smart_meter import SCMSmartMeterStrategy
from gsy_e.models.strategy.scm.storage import SCMStorageStrategy

ConstSettings.MASettings.MARKET_TYPE = SpotMarketTypeEnum.COEFFICIENTS.value

pv_profile = os.path.join(gsye_root_path, "resources", "Solar_Curve_W_sunny.csv")

prosumption_kWh_profile = {
    today(tz="UTC").set(hour=hour): 1 if hour < 12 else -1 for hour in range(0, 24)
}

consumption_kWh_profile = {
    today(tz="UTC").set(hour=hour): 0.5 for hour in range(0, 24)
}


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
                    CoefficientArea("H1 PV", strategy=SCMPVUserProfile(
                        power_profile=pv_profile)),
                    CoefficientArea("H1 Storage1", strategy=SCMStorageStrategy(
                        prosumption_kWh_profile=prosumption_kWh_profile)),
                    CoefficientArea("H1 Storage2", strategy=SCMStorageStrategy(
                        prosumption_kWh_profile=prosumption_kWh_profile)),
                ],
                coefficient_percentage=0.6
            ),
            CoefficientArea(
                "House 2",
                [
                    CoefficientArea("H2 General Load",
                                    strategy=SCMLoadHoursStrategy(avg_power_W=200,
                                                                  hrs_of_day=list(
                                                                      range(12, 16)))),
                    CoefficientArea("H2 PV", strategy=SCMPVUserProfile(
                        power_profile=pv_profile)),
                    CoefficientArea("H2 Smart Meter",
                                    strategy=SCMSmartMeterStrategy(smart_meter_profile={0: 100})),
                    CoefficientArea("H2 Heat Pump", strategy=ScmHeatPumpStrategy(
                        consumption_kWh_profile=consumption_kWh_profile))
                ],
                coefficient_percentage=0.4

            ),
        ],
        config=config
    )
    return area
