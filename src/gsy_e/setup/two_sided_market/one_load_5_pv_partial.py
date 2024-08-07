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
from gsy_e.models.strategy.pv import PVStrategy
from gsy_framework.constants_limits import ConstSettings


'''
In this test file one load with high demand is used, in order to enforce the bid that
it will place to be tokenized into smaller bids. The supply is provided by 5 PVs
with one solar panel on each, in order to not cover the load by one offer, but to
partially cover the demand with each different offer.
Expected result: when having set the log level to WARN, there should be 5 distinct trade chains
on each market slot (on market slots that PVs can provide energy though). These trades should
be a chain of bid and offer trades from the PVs to the load. For simplicity, the ma_fee is set
to 0 (it has to be set via the CLI, by configuring the cli argument ma_fee to 0), and all the
offer/bid trades should have the same energy rate (about 15 ct/kWh, depending on the
interpolation of bids and offers).
'''


def get_setup(config):
    ConstSettings.MASettings.MARKET_TYPE = 2
    ConstSettings.PVSettings.FINAL_SELLING_RATE = 0
    ConstSettings.GeneralSettings.DEFAULT_MARKET_MAKER_RATE = 30
    ConstSettings.LoadSettings.INITIAL_BUYING_RATE = 0
    ConstSettings.LoadSettings.FINAL_BUYING_RATE = 30

    area = Area(
        "Grid",
        [
            Area(
                "House 1",
                [
                    Area("H1 General Load", strategy=LoadHoursStrategy(
                        avg_power_W=1000,
                        hrs_of_day=list(range(0, 24)),
                        initial_buying_rate=ConstSettings.LoadSettings.INITIAL_BUYING_RATE,
                        final_buying_rate=ConstSettings.LoadSettings.FINAL_BUYING_RATE
                    )),
                ]
            ),
            Area(
                "House 2",
                [
                    Area("H2 PV1",
                         strategy=PVStrategy(capacity_kW=0.16)
                         ),
                    Area("H2 PV2",
                         strategy=PVStrategy(capacity_kW=0.16)
                         ),
                    Area("H2 PV3",
                         strategy=PVStrategy(capacity_kW=0.16)
                         ),
                    Area("H2 PV4",
                         strategy=PVStrategy(capacity_kW=0.16)
                         ),
                    Area("H2 PV5",
                         strategy=PVStrategy(capacity_kW=0.16)
                         ),
                ]
            ),
        ],
        config=config
    )
    return area
