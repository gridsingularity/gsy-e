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

Setup file for testing the LocalMarketOrderDispatcher via two ExternalStrategyBase instances:
- "Consumer" posts bids (buys energy) using the local market dispatcher.
- "Producer" posts offers (sells energy) using the local market dispatcher.
"""

import pendulum
from gsy_framework.constants_limits import ConstSettings
from gsy_framework.enums import AvailableMarketTypes

from gsy_e.external.external_strategy import (
    ExternalOrderInput,
    ExternalStrategyBase,
    OrderDispatchMode,
)
from gsy_e.models.area import Area


# Nominal time slot used as metadata in ExternalOrderInput; the actual delivery
# slot is determined by the simulation's spot market at runtime.
_NOMINAL_SLOT = pendulum.datetime(2024, 1, 1, 0, 0, tz="UTC")


def get_setup(config):
    ConstSettings.MASettings.MARKET_TYPE = 2
    ConstSettings.MASettings.MIN_BID_AGE = 0
    ConstSettings.MASettings.MIN_OFFER_AGE = 0

    consumer = ExternalStrategyBase(
        bid_inputs=[
            ExternalOrderInput(
                energy_kWh=1.0,
                min_price=10.0,
                max_price=50.0,
                market_type=AvailableMarketTypes.SPOT,
                time_slot=_NOMINAL_SLOT,
            ),
            ExternalOrderInput(
                energy_kWh=0.5,
                min_price=15.0,
                max_price=40.0,
                market_type=AvailableMarketTypes.SPOT,
                time_slot=_NOMINAL_SLOT,
            ),
        ],
        dispatch_mode=OrderDispatchMode.LOCAL_MARKET,
    )

    producer = ExternalStrategyBase(
        offer_inputs=[
            ExternalOrderInput(
                energy_kWh=1.5,
                min_price=10.0,
                max_price=50.0,
                market_type=AvailableMarketTypes.SPOT,
                time_slot=_NOMINAL_SLOT,
            ),
        ],
        dispatch_mode=OrderDispatchMode.LOCAL_MARKET,
    )

    area = Area(
        "Grid",
        [
            Area("Consumer", strategy=consumer),
            Area("Producer", strategy=producer),
        ],
        config=config,
    )
    return area
